alter table public.l_chat_tasks
add column if not exists action_receipt jsonb;

create or replace function public.l_task_record_action_bound(
    p_id uuid,
    p_worker uuid,
    p_hash text,
    p_request jsonb,
    p_receipt jsonb
)
returns boolean
language plpgsql
security invoker
set search_path=''
as $$
begin
    if p_receipt is null
       or jsonb_typeof(p_receipt) <> 'object'
       or p_receipt->>'request_id' <> p_id::text
       or p_receipt->>'status' <> 'confirmed'
       or coalesce(p_receipt->>'resource_id', '') = '' then
        return false;
    end if;

    update public.l_chat_tasks
       set action_receipt = p_receipt,
           checkpoint = 'connected_action_recorded',
           lease_until = now() + interval '2 minutes',
           updated_at = now()
     where request_id = p_id
       and worker_id = p_worker
       and status = 'running'
       and lease_until >= now()
       and input_hash = p_hash
       and request = p_request
       and (action_receipt is null or action_receipt = p_receipt);
    return found;
end
$$;

create or replace function public.l_task_finish_bound(
    p_id uuid,
    p_worker uuid,
    p_hash text,
    p_request jsonb,
    p_status text,
    p_result jsonb
)
returns boolean
language plpgsql
security invoker
set search_path=''
as $$
begin
    if p_status not in ('ready','failed') then
        raise exception 'Invalid terminal status';
    end if;

    update public.l_chat_tasks
       set status = p_status,
           result = p_result,
           checkpoint = p_status,
           updated_at = now()
     where request_id = p_id
       and worker_id = p_worker
       and status = 'running'
       and lease_until >= now()
       and input_hash = p_hash
       and request = p_request
       and (
            (action_receipt is null and p_result #> '{route,action_receipt}' is null)
            or (
                action_receipt is not null
                and p_result #> '{route,action_receipt}' = action_receipt
            )
       );
    return found;
end
$$;

revoke all on function public.l_task_record_action_bound(uuid,uuid,text,jsonb,jsonb)
from public, anon, authenticated;

grant execute on function public.l_task_record_action_bound(uuid,uuid,text,jsonb,jsonb)
to service_role;

revoke all on function public.l_task_finish_bound(uuid,uuid,text,jsonb,text,jsonb)
from public, anon, authenticated;

grant execute on function public.l_task_finish_bound(uuid,uuid,text,jsonb,text,jsonb)
to service_role;
