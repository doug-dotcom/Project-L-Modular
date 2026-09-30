-- Project L memory recovery: shared database cron backpressure.
--
-- Live evidence on 2026-09-30 showed the Data API emitting PGRST002 while
-- several Project L / Shine Me minute workers repeatedly failed to acquire
-- startup connections. Keep worker semantics unchanged and reduce only the
-- synchronized cadence. Other Shine applications are deliberately untouched.
--
-- The WHERE schedule guard makes this idempotent and avoids overriding later
-- operator tuning.

update cron.job
set schedule = '*/5 * * * *'
where active
  and schedule = '* * * * *'
  and command like '%private.project_l_semantic_cron_tick_v1()%';

update cron.job
set schedule = '1-59/5 * * * *'
where active
  and schedule = '* * * * *'
  and command like '%private.me_enqueue_due_trust_recovery_v1(20)%';

update cron.job
set schedule = '2-59/5 * * * *'
where active
  and schedule = '* * * * *'
  and command like '%private.me_harvest_trust_recovery_v1(50)%';

update cron.job
set schedule = '3-59/5 * * * *'
where active
  and schedule = '* * * * *'
  and command like '%private.me_reconcile_pending_activations_v1(50)%';

update cron.job
set schedule = '4-59/5 * * * *'
where active
  and schedule = '* * * * *'
  and command like '%private.me_observe_activation_reconciliation_lifecycle_v1(120)%';

update cron.job
set schedule = '*/5 * * * *'
where active
  and schedule = '* * * * *'
  and command like '%private.me_observe_activation_burn_episode_v1()%';

update cron.job
set schedule = '1-59/5 * * * *'
where active
  and schedule = '* * * * *'
  and command like '%private.me_correlate_activation_operational_events_v1(300)%';

-- Ask PostgREST to rebuild only after the connection stampede has been reduced.
notify pgrst, 'reload schema';
