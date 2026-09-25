create function public.l_task_progress_bound(
    p_id uuid,
    p_worker uuid,
    p_hash text,
    p_request jsonb,
    p_checkpoint text default null
)
returns boolean
language plpgsql
security invoker
set search_path=''
as $$
begin
    update public.l_chat_tasks
       set lease_until = now() + interval '2 minutes',
           checkpoint = coalesce(p_checkpoint, checkpoint),
           updated_at = now()
     where request_id = p_id
       and worker_id = p_worker
       and status = 'running'
       and lease_until >= now()
       and input_hash = p_hash
       and request = p_request;
    return found;
end
$$;

create function public.l_task_finish_bound(
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
       and request = p_request;
    return found;
end
$$;

revoke all on function public.l_task_progress_bound(uuid,uuid,text,jsonb,text)
from public, anon, authenticated;

revoke all on function public.l_task_finish_bound(uuid,uuid,text,jsonb,text,jsonb)
from public, anon, authenticated;

grant execute on function public.l_task_progress_bound(uuid,uuid,text,jsonb,text)
to service_role;

grant execute on function public.l_task_finish_bound(uuid,uuid,text,jsonb,text,jsonb)
to service_role;
