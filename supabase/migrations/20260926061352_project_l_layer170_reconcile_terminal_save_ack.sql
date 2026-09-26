create or replace function public.l_task_confirm_finish_bound(
    p_id uuid,
    p_worker uuid,
    p_hash text,
    p_request jsonb,
    p_status text,
    p_result jsonb
)
returns boolean
language sql
security invoker
set search_path=''
stable
as $function$
    select
        p_status in ('ready', 'failed')
        and exists (
            select 1
            from public.l_chat_tasks
            where request_id = p_id
              and worker_id = p_worker
              and status = p_status
              and checkpoint = p_status
              and input_hash = p_hash
              and request = p_request
              and result = p_result
              and (
                    (action_receipt is null and p_result #> '{route,action_receipt}' is null)
                    or (
                        action_receipt is not null
                        and p_result #> '{route,action_receipt}' = action_receipt
                    )
              )
        );
$function$;

revoke execute on function public.l_task_confirm_finish_bound(
    uuid, uuid, text, jsonb, text, jsonb
) from public, anon, authenticated;

grant execute on function public.l_task_confirm_finish_bound(
    uuid, uuid, text, jsonb, text, jsonb
) to service_role;
