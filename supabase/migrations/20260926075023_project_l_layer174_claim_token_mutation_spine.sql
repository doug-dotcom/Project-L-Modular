-- Layer 174 foundation: claim-token-bind every post-claim mutation.
create or replace function public.l_task_progress_claim_bound(p_id uuid,p_worker uuid,p_claim_token uuid,p_hash text,p_request jsonb,p_checkpoint text default null)
returns boolean language plpgsql security invoker set search_path='' as $$ begin
update public.l_chat_tasks set lease_until=now()+interval '2 minutes',checkpoint=coalesce(p_checkpoint,checkpoint),updated_at=now()
where request_id=p_id and worker_id=p_worker and claim_token=p_claim_token and p_claim_token is not null
and status='running' and lease_until>=now() and input_hash=p_hash and request=p_request; return found; end $$;
create or replace function public.l_task_record_action_claim_bound(p_id uuid,p_worker uuid,p_claim_token uuid,p_hash text,p_request jsonb,p_receipt jsonb)
returns boolean language plpgsql security invoker set search_path='' as $$ begin
if p_receipt is null or jsonb_typeof(p_receipt)<>'object' or p_receipt->>'request_id'<>p_id::text or p_receipt->>'status'<>'confirmed' or coalesce(p_receipt->>'resource_id','')='' then return false; end if;
update public.l_chat_tasks set action_receipt=p_receipt,checkpoint='connected_action_recorded',lease_until=now()+interval '2 minutes',updated_at=now()
where request_id=p_id and worker_id=p_worker and claim_token=p_claim_token and p_claim_token is not null and status='running' and lease_until>=now()
and input_hash=p_hash and request=p_request and (action_receipt is null or action_receipt=p_receipt); return found; end $$;
create or replace function public.l_task_confirm_action_claim_bound(p_id uuid,p_worker uuid,p_claim_token uuid,p_hash text,p_request jsonb,p_receipt jsonb)
returns boolean language sql security invoker set search_path='' stable as $$ select exists(select 1 from public.l_chat_tasks where request_id=p_id and worker_id=p_worker and claim_token=p_claim_token and p_claim_token is not null and status='running' and lease_until>=now() and input_hash=p_hash and request=p_request and action_receipt=p_receipt); $$;
create or replace function public.l_task_finish_claim_bound(p_id uuid,p_worker uuid,p_claim_token uuid,p_hash text,p_request jsonb,p_status text,p_result jsonb)
returns boolean language plpgsql security invoker set search_path='' as $$ begin
if p_status not in ('ready','failed') then raise exception 'Invalid terminal status'; end if;
update public.l_chat_tasks set status=p_status,result=p_result,checkpoint=p_status,updated_at=now()
where request_id=p_id and worker_id=p_worker and claim_token=p_claim_token and p_claim_token is not null and status='running' and lease_until>=now() and input_hash=p_hash and request=p_request
and ((action_receipt is null and p_result #> '{route,action_receipt}' is null) or (action_receipt is not null and p_result #> '{route,action_receipt}'=action_receipt)); return found; end $$;
create or replace function public.l_task_confirm_finish_claim_bound(p_id uuid,p_worker uuid,p_claim_token uuid,p_hash text,p_request jsonb,p_status text,p_result jsonb)
returns boolean language sql security invoker set search_path='' stable as $$ select p_status in ('ready','failed') and exists(select 1 from public.l_chat_tasks where request_id=p_id and worker_id=p_worker and claim_token=p_claim_token and p_claim_token is not null and status=p_status and checkpoint=p_status and input_hash=p_hash and request=p_request and result=p_result and ((action_receipt is null and p_result #> '{route,action_receipt}' is null) or (action_receipt is not null and p_result #> '{route,action_receipt}'=action_receipt))); $$;
create or replace function public.l_task_reject_claim_bound(p_id uuid,p_worker uuid,p_claim_token uuid,p_hash text,p_request jsonb,p_result jsonb)
returns boolean language plpgsql security invoker set search_path='' as $$ begin
update public.l_chat_tasks set status='failed',result=p_result,checkpoint='failed',updated_at=now()
where request_id=p_id and worker_id=p_worker and claim_token=p_claim_token and p_claim_token is not null and status='running' and lease_until>=now()
and input_hash=p_hash and request=p_request and checkpoint='starting' and result is null and action_receipt is null
and jsonb_typeof(p_result)='object' and p_result @> '{"error": true}'::jsonb and jsonb_typeof(p_result->'reply')='string' and p_result #> '{route,action_receipt}' is null; return found; end $$;
revoke execute on function public.l_task_progress_claim_bound(uuid,uuid,uuid,text,jsonb,text) from public,anon,authenticated;
revoke execute on function public.l_task_record_action_claim_bound(uuid,uuid,uuid,text,jsonb,jsonb) from public,anon,authenticated;
revoke execute on function public.l_task_confirm_action_claim_bound(uuid,uuid,uuid,text,jsonb,jsonb) from public,anon,authenticated;
revoke execute on function public.l_task_finish_claim_bound(uuid,uuid,uuid,text,jsonb,text,jsonb) from public,anon,authenticated;
revoke execute on function public.l_task_confirm_finish_claim_bound(uuid,uuid,uuid,text,jsonb,text,jsonb) from public,anon,authenticated;
revoke execute on function public.l_task_reject_claim_bound(uuid,uuid,uuid,text,jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.l_task_progress_claim_bound(uuid,uuid,uuid,text,jsonb,text) to service_role;
grant execute on function public.l_task_record_action_claim_bound(uuid,uuid,uuid,text,jsonb,jsonb) to service_role;
grant execute on function public.l_task_confirm_action_claim_bound(uuid,uuid,uuid,text,jsonb,jsonb) to service_role;
grant execute on function public.l_task_finish_claim_bound(uuid,uuid,uuid,text,jsonb,text,jsonb) to service_role;
grant execute on function public.l_task_confirm_finish_claim_bound(uuid,uuid,uuid,text,jsonb,text,jsonb) to service_role;
grant execute on function public.l_task_reject_claim_bound(uuid,uuid,uuid,text,jsonb,jsonb) to service_role;
