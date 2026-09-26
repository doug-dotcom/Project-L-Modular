create or replace function public.l_task_reap_expired(
    p_limit integer default 100
)
returns integer
language plpgsql
security invoker
set search_path=''
as $function$
declare
    changed integer := 0;
    safe_limit integer;
begin
    safe_limit := greatest(1, least(coalesce(p_limit, 100), 500));
    with expired as (
        select request_id
        from public.l_chat_tasks
        where status = 'running' and lease_until < now()
        order by lease_until, request_id
        for update skip locked
        limit safe_limit
    )
    update public.l_chat_tasks as t
       set status = 'interrupted', updated_at = now()
      from expired
     where t.request_id = expired.request_id
       and t.status = 'running'
       and t.lease_until < now();
    get diagnostics changed = row_count;
    return changed;
end
$function$;

create or replace function public.l_task_claim_bound(
    p_worker uuid,
    p_claim_token uuid
)
returns setof public.l_chat_tasks
language plpgsql
security invoker
set search_path=''
as $function$
begin
    if p_worker is null or p_claim_token is null then return; end if;
    return query select * from public.l_chat_tasks
     where status='running' and worker_id=p_worker and claim_token=p_claim_token
       and lease_until >= now() limit 1;
    if found then return; end if;
    if exists(select 1 from public.l_chat_tasks where status='running'
              and worker_id=p_worker and lease_until >= now()) then return; end if;
    if exists(select 1 from public.l_chat_tasks where claim_token=p_claim_token) then return; end if;
    begin
        return query
        update public.l_chat_tasks
           set status='running',checkpoint='starting',worker_id=p_worker,
               claim_token=p_claim_token,lease_until=now()+interval '2 minutes',updated_at=now()
         where request_id=(select request_id from public.l_chat_tasks where status='queued'
                           order by created_at for update skip locked limit 1)
        returning *;
    exception when unique_violation then
        return query select * from public.l_chat_tasks
         where status='running' and worker_id=p_worker and claim_token=p_claim_token
           and lease_until >= now() limit 1;
        return;
    end;
end
$function$;

revoke execute on function public.l_task_reap_expired(integer)
from public, anon, authenticated;
grant execute on function public.l_task_reap_expired(integer)
to service_role;
