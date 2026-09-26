alter table public.l_chat_tasks
    add column if not exists claim_token uuid;

create unique index if not exists l_chat_tasks_claim_token_unique
    on public.l_chat_tasks(claim_token)
    where claim_token is not null;

create unique index if not exists l_chat_tasks_one_running_per_worker
    on public.l_chat_tasks(worker_id)
    where status='running' and worker_id is not null;

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
    if p_worker is null or p_claim_token is null then
        return;
    end if;

    update public.l_chat_tasks
       set status='interrupted',
           updated_at=now()
     where status='running'
       and lease_until < now();

    return query
    select *
      from public.l_chat_tasks
     where status='running'
       and worker_id=p_worker
       and claim_token=p_claim_token
       and lease_until >= now()
     limit 1;
    if found then
        return;
    end if;

    if exists (
        select 1
          from public.l_chat_tasks
         where status='running'
           and worker_id=p_worker
           and lease_until >= now()
    ) then
        return;
    end if;

    if exists (
        select 1
          from public.l_chat_tasks
         where claim_token=p_claim_token
    ) then
        return;
    end if;

    begin
        return query
        update public.l_chat_tasks
           set status='running',
               checkpoint='starting',
               worker_id=p_worker,
               claim_token=p_claim_token,
               lease_until=now()+interval '2 minutes',
               updated_at=now()
         where request_id=(
             select request_id
               from public.l_chat_tasks
              where status='queued'
              order by created_at
              for update skip locked
              limit 1
         )
        returning *;
    exception
        when unique_violation then
            return query
            select *
              from public.l_chat_tasks
             where status='running'
               and worker_id=p_worker
               and claim_token=p_claim_token
               and lease_until >= now()
             limit 1;
            return;
    end;
end
$function$;

revoke execute on function public.l_task_claim_bound(uuid, uuid)
from public, anon, authenticated;

grant execute on function public.l_task_claim_bound(uuid, uuid)
to service_role;
