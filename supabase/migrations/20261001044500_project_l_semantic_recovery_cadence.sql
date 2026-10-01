-- Project L semantic recovery cadence.
--
-- Production evidence on 2026-10-01 showed the shared Shine-L database in a
-- sustained cron-startup storm. Project L's semantic tick and semantic circuit
-- breaker were both scheduled every five minutes and repeatedly failed to
-- acquire startup connections alongside unrelated estate workloads.
--
-- Live owner-scoped recall does not depend on these background semantic jobs.
-- Reduce Project L's contribution to the shared cron load by moving each job to
-- a staggered 15-minute cadence. The already-staggered activation preflight is
-- deliberately unchanged, and no Fiona, Rivers, or Shine Me job is modified.

do $migration$
declare
    target record;
begin
    for target in
        select jobid
        from cron.job
        where active
          and schedule = '*/5 * * * *'
          and command like '%private.project_l_semantic_cron_tick_v1()%'
    loop
        perform cron.alter_job(
            job_id := target.jobid,
            schedule := '7-59/15 * * * *'
        );
    end loop;

    for target in
        select jobid
        from cron.job
        where active
          and schedule = '*/5 * * * *'
          and command like '%private.project_l_semantic_circuit_breaker_v1()%'
    loop
        perform cron.alter_job(
            job_id := target.jobid,
            schedule := '12-59/15 * * * *'
        );
    end loop;
end
$migration$;

notify pgrst, 'reload schema';
