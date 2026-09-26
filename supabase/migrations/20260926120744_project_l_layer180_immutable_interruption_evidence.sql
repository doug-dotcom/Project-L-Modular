create or replace function public.l_task_guard_interruption_evidence()
returns trigger
language plpgsql
security invoker
set search_path=''
as $function$
begin
    if old.interruption_evidence is not null
       and new.interruption_evidence is distinct from old.interruption_evidence then
        raise exception 'interruption_evidence is immutable once recorded'
            using errcode = '23514';
    end if;

    if old.interruption_evidence is null
       and new.interruption_evidence is not null then
        if old.status <> 'running'
           or new.status <> 'interrupted'
           or new.interruption_evidence->>'reason' <> 'lease_expired'
           or new.interruption_evidence->>'version' <> '1.0'
           or new.interruption_evidence->>'checkpoint' is distinct from old.checkpoint
           or new.interruption_evidence->>'worker_id' is distinct from old.worker_id::text
           or new.interruption_evidence->>'claim_token' is distinct from old.claim_token::text
           or new.interruption_evidence->>'action_journalled'
                is distinct from (old.action_receipt is not null)::text
        then
            raise exception 'invalid interruption_evidence transition'
                using errcode = '23514';
        end if;
    end if;
    return new;
end
$function$;

drop trigger if exists l_chat_tasks_guard_interruption_evidence
on public.l_chat_tasks;

create trigger l_chat_tasks_guard_interruption_evidence
before update of interruption_evidence on public.l_chat_tasks
for each row
execute function public.l_task_guard_interruption_evidence();

revoke execute on function public.l_task_guard_interruption_evidence()
from public, anon, authenticated, service_role;
