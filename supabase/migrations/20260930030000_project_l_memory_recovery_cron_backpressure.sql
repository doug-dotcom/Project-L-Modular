-- Project L memory recovery: shared database cron backpressure.
--
-- Live evidence on 2026-09-30 showed the Data API emitting PGRST002 while
-- several Project L / Shine Me minute workers repeatedly failed to acquire
-- startup connections. Keep worker semantics unchanged and reduce only the
-- synchronized cadence. Other Shine applications are deliberately untouched.
--
-- Use Supabase Cron's supported cron.alter_job() surface rather than updating
-- cron.job directly. The schedule guard keeps this idempotent and avoids
-- overriding later operator tuning.

do $migration$
declare
    target record;
begin
    for target in
        select jobid
        from cron.job
        where active
          and schedule = '* * * * *'
          and command like '%private.project_l_semantic_cron_tick_v1()%'
    loop
        perform cron.alter_job(
            job_id := target.jobid,
            schedule := '*/5 * * * *'
        );
    end loop;

    for target in
        select jobid
        from cron.job
        where active
          and schedule = '* * * * *'
          and command like '%private.me_enqueue_due_trust_recovery_v1(20)%'
    loop
        perform cron.alter_job(
            job_id := target.jobid,
            schedule := '1-59/5 * * * *'
        );
    end loop;

    for target in
        select jobid
        from cron.job
        where active
          and schedule = '* * * * *'
          and command like '%private.me_harvest_trust_recovery_v1(50)%'
    loop
        perform cron.alter_job(
            job_id := target.jobid,
            schedule := '2-59/5 * * * *'
        );
    end loop;

    for target in
        select jobid
        from cron.job
        where active
          and schedule = '* * * * *'
          and command like '%private.me_reconcile_pending_activations_v1(50)%'
    loop
        perform cron.alter_job(
            job_id := target.jobid,
            schedule := '3-59/5 * * * *'
        );
    end loop;

    for target in
        select jobid
        from cron.job
        where active
          and schedule = '* * * * *'
          and command like '%private.me_observe_activation_reconciliation_lifecycle_v1(120)%'
    loop
        perform cron.alter_job(
            job_id := target.jobid,
            schedule := '4-59/5 * * * *'
        );
    end loop;

    for target in
        select jobid
        from cron.job
        where active
          and schedule = '* * * * *'
          and command like '%private.me_observe_activation_burn_episode_v1()%'
    loop
        perform cron.alter_job(
            job_id := target.jobid,
            schedule := '*/5 * * * *'
        );
    end loop;

    for target in
        select jobid
        from cron.job
        where active
          and schedule = '* * * * *'
          and command like '%private.me_correlate_activation_operational_events_v1(300)%'
    loop
        perform cron.alter_job(
            job_id := target.jobid,
            schedule := '1-59/5 * * * *'
        );
    end loop;
end
$migration$;

notify pgrst, 'reload schema';
