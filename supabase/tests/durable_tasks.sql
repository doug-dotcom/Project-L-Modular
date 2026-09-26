-- Run against an idle test database with the Stage 2 migration applied.
-- Every assertion is rolled back; the queue lock prevents concurrent consumption.
begin;
lock table public.l_chat_tasks in share row exclusive mode;
do $$
declare
 id uuid:=gen_random_uuid(); u uuid:=gen_random_uuid(); w uuid:=gen_random_uuid();
 ct uuid:=gen_random_uuid();
 r jsonb; t public.l_chat_tasks; receipt jsonb; other_receipt jsonb;
begin
 assert not exists(select 1 from public.l_chat_tasks where status in ('queued','running')), 'Use an idle test database';
 r:=public.l_task_submit(id,u,repeat('a',64),'hash','{"message":"synthetic test"}');
 assert r->>'status'='queued';
 r:=public.l_task_submit(id,u,repeat('a',64),'hash','{}');
 assert r->>'status'='queued';
 r:=public.l_task_submit(id,u,repeat('a',64),'changed','{}');
 assert r->>'status'='conflict';
 r:=public.l_task_submit(id,u,repeat('b',64),'hash','{}');
 assert r->>'status'='not_found';
 select * into t from public.l_task_claim_bound(w,ct);
 assert t.request_id=id;
 assert (select request_id from public.l_task_claim_bound(w,ct))=id;
 assert not exists(select 1 from public.l_task_claim_bound(w,gen_random_uuid()));
 assert not exists(select 1 from public.l_task_claim_bound(gen_random_uuid(),gen_random_uuid()));
 assert not public.l_task_finish_bound(id,gen_random_uuid(),'hash',t.request,'ready','{}');
 assert not public.l_task_progress_bound(id,w,'changed',t.request,'wrong_hash');
 assert not public.l_task_progress_bound(id,w,'hash','{}'::jsonb,'wrong_request');
 assert public.l_task_progress_bound(id,w,'hash',t.request,'bound_checkpoint');
 assert public.l_task_progress_bound(id,w,'hash',t.request,'test_checkpoint');

 receipt:=jsonb_build_object(
   'version','layer165-connected-action-receipt-1',
   'status','confirmed',
   'request_id',id::text,
   'request_bound',true,
   'capability','google_tasks',
   'action','create',
   'resource_id','synthetic-task-167',
   'subject_sha256',repeat('c',64),
   'receipt_sha256',repeat('d',64)
 );
 other_receipt:=jsonb_set(receipt,'{resource_id}','"different-task"'::jsonb);

 assert not public.l_task_record_action_bound(id,gen_random_uuid(),'hash',t.request,receipt);
 assert not public.l_task_record_action_bound(id,w,'changed',t.request,receipt);
 assert not public.l_task_record_action_bound(id,w,'hash','{}'::jsonb,receipt);
 assert public.l_task_record_action_bound(id,w,'hash',t.request,receipt);
 assert (select action_receipt from public.l_chat_tasks where request_id=id)=receipt;
 assert public.l_task_record_action_bound(id,w,'hash',t.request,receipt);
 assert not public.l_task_record_action_bound(id,w,'hash',t.request,other_receipt);

 assert not public.l_task_finish_bound(id,w,'hash',t.request,'ready','{"reply":"missing journal"}');
 assert not public.l_task_finish_bound(
   id,w,'hash',t.request,'ready',
   jsonb_build_object('reply','wrong journal','route',jsonb_build_object('action_receipt',other_receipt))
 );
 assert public.l_task_finish_bound(
   id,w,'hash',t.request,'ready',
   jsonb_build_object('reply','saved result','route',jsonb_build_object('action_receipt',receipt))
 );
 assert (select result->>'reply' from public.l_chat_tasks where request_id=id)='saved result';
 assert not public.l_task_finish_bound(id,w,'hash',t.request,'failed','{}');
 update public.l_chat_tasks set status='running',lease_until=now()-interval '3 minutes' where request_id=id;
 perform public.l_task_claim_bound(gen_random_uuid(),gen_random_uuid());
 assert (select status from public.l_chat_tasks where request_id=id)='interrupted';
 assert not public.l_task_progress_bound(id,w,'hash',t.request,null);
 assert not has_table_privilege('anon','public.l_chat_tasks','select');
 assert not has_table_privilege('authenticated','public.l_chat_tasks','select');
 assert not has_function_privilege('anon','public.l_task_claim(uuid)','execute');
 assert not has_function_privilege('authenticated','public.l_task_claim(uuid)','execute');
 assert not has_function_privilege('service_role','public.l_task_claim(uuid)','execute');
 assert not has_function_privilege('anon','public.l_task_claim_bound(uuid,uuid)','execute');
 assert not has_function_privilege('authenticated','public.l_task_claim_bound(uuid,uuid)','execute');
 assert has_function_privilege('service_role','public.l_task_claim_bound(uuid,uuid)','execute');
 assert not has_function_privilege('authenticated','public.l_task_submit(uuid,uuid,text,text,jsonb)','execute');
 assert not has_function_privilege('anon','public.l_task_progress_bound(uuid,uuid,text,jsonb,text)','execute');
 assert not has_function_privilege('authenticated','public.l_task_finish_bound(uuid,uuid,text,jsonb,text,jsonb)','execute');
 assert not has_function_privilege('anon','public.l_task_record_action_bound(uuid,uuid,text,jsonb,jsonb)','execute');
 assert not has_function_privilege('authenticated','public.l_task_record_action_bound(uuid,uuid,text,jsonb,jsonb)','execute');
 assert has_function_privilege('service_role','public.l_task_record_action_bound(uuid,uuid,text,jsonb,jsonb)','execute');
 assert has_function_privilege('service_role','public.l_task_progress_bound(uuid,uuid,text,jsonb,text)','execute');
 assert has_function_privilege('service_role','public.l_task_finish_bound(uuid,uuid,text,jsonb,text,jsonb)','execute');
 assert has_function_privilege('service_role','public.l_task_reject_bound(uuid,uuid,text,jsonb,jsonb)','execute');
 assert not has_function_privilege('anon','public.l_task_reject_bound(uuid,uuid,text,jsonb,jsonb)','execute');
 assert not has_function_privilege('service_role','public.l_task_progress(uuid,uuid,text)','execute');
 assert not has_function_privilege('service_role','public.l_task_finish(uuid,uuid,text,jsonb)','execute');
end $$;
rollback;
