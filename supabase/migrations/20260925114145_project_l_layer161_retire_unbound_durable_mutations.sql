create function public.l_task_reject_bound(
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
as $$
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
       and request = p_request;
    return found;
end
$$;

revoke all on function public.l_task_reject_bound(uuid,uuid,text,jsonb,jsonb)
from public, anon, authenticated;

grant execute on function public.l_task_reject_bound(uuid,uuid,text,jsonb,jsonb)
to service_role;

revoke execute on function public.l_task_progress(uuid,uuid,text)
from service_role;

revoke execute on function public.l_task_finish(uuid,uuid,text,jsonb)
from service_role;
