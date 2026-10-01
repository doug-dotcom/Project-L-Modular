-- Project L semantic background yield.
--
-- Live production evidence on 2026-10-01 showed Project L's owner-scoped
-- memory RPC timing out while semantic background work and shared database
-- maintenance were contending for Postgres. Keep live recall's strict timeout
-- unchanged. Instead, bound the semantic resource-limit probe to recent
-- dispatches first and stagger the 15-minute activation preflight away from
-- the 5-minute semantic worker.
--
-- The helper remains fail-closed: if a recent pg_net response is HTTP 546 the
-- semantic worker stays in resource-limit cooldown.

create or replace function private.project_l_semantic_recent_resource_limit_v1()
returns boolean
language plpgsql
stable
security definer
set search_path = ''
as $function$
declare
    v_cooldown_minutes integer := 30;
begin
    select least(
        greatest(coalesce(resource_limit_cooldown_minutes, 30), 1),
        1440
    )
    into v_cooldown_minutes
    from private.l_semantic_worker_runtime_policy
    where singleton = true;

    return exists(
        with recent_dispatches as materialized (
            select request_id
            from private.l_semantic_worker_dispatches
            where created_at >= now() - make_interval(
                mins => v_cooldown_minutes
            )
            order by created_at desc
            limit 64
        )
        select 1
        from net._http_response r
        join recent_dispatches d
          on d.request_id = r.id
        where r.status_code = 546
    );
end;
$function$;

revoke all on function private.project_l_semantic_recent_resource_limit_v1()
    from public, anon, authenticated;
grant execute on function private.project_l_semantic_recent_resource_limit_v1()
    to service_role;

do $migration$
declare
    target record;
begin
    for target in
        select jobid
        from cron.job
        where active
          and schedule = '*/15 * * * *'
          and command like '%private.project_l_semantic_activation_preflight_v1()%'
    loop
        perform cron.alter_job(
            job_id := target.jobid,
            schedule := '2-59/15 * * * *'
        );
    end loop;
end
$migration$;

notify pgrst, 'reload schema';
