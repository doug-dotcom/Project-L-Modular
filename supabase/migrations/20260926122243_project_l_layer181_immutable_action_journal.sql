create or replace function public.l_task_guard_action_receipt()
returns trigger
language plpgsql
security invoker
set search_path=''
as $function$
begin
    if old.action_receipt is not null
       and new.action_receipt is distinct from old.action_receipt then
        raise exception 'action_receipt is immutable once recorded'
            using errcode = '23514';
    end if;

    if old.action_receipt is null
       and new.action_receipt is not null then
        if old.status <> 'running'
           or new.status <> 'running'
           or new.action_receipt->>'request_id' is distinct from old.request_id::text
           or new.action_receipt->>'status' <> 'confirmed'
           or coalesce(new.action_receipt->>'resource_id','') = ''
           or new.checkpoint <> 'connected_action_recorded'
        then
            raise exception 'invalid action_receipt transition'
                using errcode = '23514';
        end if;
    end if;
    return new;
end
$function$;

drop trigger if exists l_chat_tasks_guard_action_receipt
on public.l_chat_tasks;

create trigger l_chat_tasks_guard_action_receipt
before update of action_receipt on public.l_chat_tasks
for each row
execute function public.l_task_guard_action_receipt();

revoke execute on function public.l_task_guard_action_receipt()
from public, anon, authenticated, service_role;
