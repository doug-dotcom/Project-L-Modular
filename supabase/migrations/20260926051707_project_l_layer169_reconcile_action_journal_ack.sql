create or replace function public.l_task_confirm_action_bound(
    p_id uuid,
    p_worker uuid,
    p_hash text,
    p_request jsonb,
    p_receipt jsonb
)
returns boolean
language sql
security invoker
set search_path=''
stable
as $function$
    select exists (
        select 1
        from public.l_chat_tasks
        where request_id = p_id
          and worker_id = p_worker
          and status = 'running'
          and lease_until >= now()
          and input_hash = p_hash
          and request = p_request
          and action_receipt = p_receipt
    );
$function$;

revoke execute on function public.l_task_confirm_action_bound(uuid, uuid, text, jsonb, jsonb)
from public, anon, authenticated;

grant execute on function public.l_task_confirm_action_bound(uuid, uuid, text, jsonb, jsonb)
to service_role;
