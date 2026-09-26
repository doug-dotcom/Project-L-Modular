create or replace function public.l_task_recover_bound(
    p_id uuid,
    p_user uuid,
    p_owner text
)
returns table(
    status text,
    result jsonb,
    action_receipt jsonb,
    request jsonb,
    input_hash text,
    checkpoint text,
    lease_until timestamptz,
    created_at timestamptz,
    updated_at timestamptz
)
language sql
security invoker
set search_path=''
stable
as $function$
    select
        t.status,
        t.result,
        t.action_receipt,
        t.request,
        t.input_hash,
        t.checkpoint,
        t.lease_until,
        t.created_at,
        t.updated_at
    from public.l_chat_tasks as t
    where t.request_id = p_id
      and t.user_id = p_user
      and t.owner_hash = p_owner
      and p_owner is not null
      and length(p_owner) = 64
      and p_owner ~ '^[0-9a-f]{64}$'
    limit 1;
$function$;

revoke execute on function public.l_task_recover_bound(uuid,uuid,text)
from public, anon, authenticated;

grant execute on function public.l_task_recover_bound(uuid,uuid,text)
to service_role;
