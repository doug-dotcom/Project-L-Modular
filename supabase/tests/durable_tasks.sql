-- Run against an idle test database with the Stage 2 migration applied.
-- Every assertion is rolled back; the queue lock prevents concurrent consumption.
begin;
lock table public.l_chat_tasks in share row exclusive mode;
do $$
declare
 id uuid:=gen_random_uuid(); u uuid:=gen_random_uuid(); w uuid:=gen_random_uuid();
 r jsonb; t public.l_chat_tasks;
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
 select * into t from public.l_task_claim(w);
 assert t.request_id=id;
 assert not exists(select 1 from public.l_task_claim(gen_random_uuid()));
 assert not public.l_task_finish(id,gen_random_uuid(),'ready','{}');
 assert public.l_task_progress(id,w,'test_checkpoint');
 assert public.l_task_finish(id,w,'ready','{"reply":"saved result"}');
 assert (select result->>'reply' from public.l_chat_tasks where request_id=id)='saved result';
 assert not public.l_task_finish(id,w,'failed','{}');
 update public.l_chat_tasks set status='running',lease_until=now()-interval '3 minutes' where request_id=id;
 perform public.l_task_claim(gen_random_uuid());
 assert (select status from public.l_chat_tasks where request_id=id)='interrupted';
 assert not public.l_task_progress(id,w);
 assert not has_table_privilege('anon','public.l_chat_tasks','select');
 assert not has_table_privilege('authenticated','public.l_chat_tasks','select');
 assert not has_function_privilege('anon','public.l_task_claim(uuid)','execute');
 assert not has_function_privilege('authenticated','public.l_task_submit(uuid,uuid,text,text,jsonb)','execute');
end $$;
rollback;
