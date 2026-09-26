create or replace function public.l_task_reject_bound(
    p_id uuid,
    p_worker uuid,
    p_hash text,
    p_request jsonb,
    p_result jsonb
)
returns boolean
language plpgsql
security invoker
set search_path=''
as $function$
begin
    update public.l_chat_tasks
       set status = 'failed',
           result = p_result,
           checkpoint = 'failed',
           updated_at = now()
     where request_id = p_id
       and worker_id = p_worker
       and status = 'running'
       and lease_until >= now()
       and input_hash = p_hash
       and request = p_request
       and claim_token is not null
       and checkpoint = 'starting'
       and result is null
       and action_receipt is null
       and jsonb_typeof(p_result) = 'object'
       and p_result @> '{"error": true}'::jsonb
       and jsonb_typeof(p_result->'reply') = 'string'
       and p_result #> '{route,action_receipt}' is null;
    return found;
end
$function$;

comment on function public.l_task_reject_bound(uuid,uuid,text,jsonb,jsonb) is
  'Layer 173 pre-execution rejection only: exact token-bound live claim, starting checkpoint, no prior result/action journal, error payload without connected-action receipt.';

revoke execute on function public.l_task_reject_bound(uuid,uuid,text,jsonb,jsonb)
from public, anon, authenticated;

grant execute on function public.l_task_reject_bound(uuid,uuid,text,jsonb,jsonb)
to service_role;
