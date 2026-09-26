alter table public.l_chat_tasks
    add column if not exists interruption_evidence jsonb;

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
       set status = 'interrupted',
           interruption_evidence = jsonb_build_object(
               'version','1.0',
               'reason','lease_expired',
               'interrupted_at',now(),
               'lease_until',t.lease_until,
               'checkpoint',t.checkpoint,
               'worker_id',t.worker_id,
               'claim_token',t.claim_token,
               'action_journalled',(t.action_receipt is not null)
           ),
           updated_at = now()
      from expired
     where t.request_id=expired.request_id
       and t.status='running'
       and t.lease_until<now()
       and t.interruption_evidence is null;
    get diagnostics changed = row_count;
    return changed;
end
$function$;

comment on column public.l_chat_tasks.interruption_evidence is
  'Layer 178 immutable forensic evidence captured when a live durable task becomes interrupted.';

revoke execute on function public.l_task_reap_expired(integer)
from public, anon, authenticated;
grant execute on function public.l_task_reap_expired(integer)
to service_role;
