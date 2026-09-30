-- Project L Layer 293 — transactional acceptance tests
begin;

do $test$
declare
  t timestamptz := '2026-09-29 01:00:00+00';
  u_allowed uuid := '29300000-0000-4000-8000-000000000001';
  u_burst uuid := '29300000-0000-4000-8000-000000000002';
  u_days uuid := '29300000-0000-4000-8000-000000000003';
  u_stale uuid := '29300000-0000-4000-8000-000000000004';
  u_cooldown uuid := '29300000-0000-4000-8000-000000000005';
  u_osc uuid := '29300000-0000-4000-8000-000000000006';
  valid_outcomes jsonb;
  result jsonb;
begin
  valid_outcomes := jsonb_build_array(
    jsonb_build_object('mode','lexical','score',0.50,'served',true,'served_at',t-interval '96 hours'),
    jsonb_build_object('mode','lexical','score',0.52,'served',true,'served_at',t-interval '72 hours'),
    jsonb_build_object('mode','lexical','score',0.48,'served',true,'served_at',t-interval '50 hours'),
    jsonb_build_object('mode','lexical','score',0.51,'served',true,'served_at',t-interval '27 hours'),
    jsonb_build_object('mode','lexical','score',0.49,'served',true,'served_at',t-interval '2 hours'),
    jsonb_build_object('mode','hybrid','score',0.91,'served',true,'served_at',t-interval '96 hours'),
    jsonb_build_object('mode','hybrid','score',0.92,'served',true,'served_at',t-interval '72 hours'),
    jsonb_build_object('mode','hybrid','score',0.90,'served',true,'served_at',t-interval '50 hours'),
    jsonb_build_object('mode','hybrid','score',0.93,'served',true,'served_at',t-interval '27 hours'),
    jsonb_build_object('mode','hybrid','score',0.94,'served',true,'served_at',t-interval '2 hours')
  );

  -- Stable, fresh, multi-day evidence may switch.
  result := public.project_l_adaptive_strategy_drift_guard_v1(
    u_allowed,'general_recall','lexical','hybrid',valid_outcomes,t
  );
  assert (result->>'allowed')::boolean, 'valid evidence should be allowed';
  assert (result->>'eventRecorded')::boolean, 'allowed switch should record one event';

  -- Same preference request is idempotent.
  result := public.project_l_adaptive_strategy_drift_guard_v1(
    u_allowed,'general_recall','lexical','hybrid',valid_outcomes,t+interval '1 minute'
  );
  assert result->>'status' = 'already_preferred', 'same preference should be idempotent';
  assert not (result->>'eventRecorded')::boolean, 'duplicate preference must not record';
  assert (
    select count(*) from public.project_l_retrieval_adaptation_events
    where user_id=u_allowed and intent='general_recall'
  ) = 1, 'duplicate preference created more than one event';

  -- One burst of outcomes must not drive adaptation.
  result := public.project_l_adaptive_strategy_drift_guard_v1(
    u_burst,'general_recall','lexical','hybrid',
    jsonb_build_array(
      jsonb_build_object('mode','lexical','score',0.50,'served',true,'served_at',t-interval '96 hours'),
      jsonb_build_object('mode','lexical','score',0.50,'served',true,'served_at',t-interval '72 hours'),
      jsonb_build_object('mode','lexical','score',0.50,'served',true,'served_at',t-interval '48 hours'),
      jsonb_build_object('mode','lexical','score',0.50,'served',true,'served_at',t-interval '30 hours'),
      jsonb_build_object('mode','lexical','score',0.50,'served',true,'served_at',t-interval '26 hours'),
      jsonb_build_object('mode','hybrid','score',0.95,'served',true,'served_at',t-interval '23 hours'),
      jsonb_build_object('mode','hybrid','score',0.95,'served',true,'served_at',t-interval '18 hours'),
      jsonb_build_object('mode','hybrid','score',0.95,'served',true,'served_at',t-interval '12 hours'),
      jsonb_build_object('mode','hybrid','score',0.95,'served',true,'served_at',t-interval '6 hours'),
      jsonb_build_object('mode','hybrid','score',0.95,'served',true,'served_at',t-interval '1 hour')
    ),t
  );
  assert not (result->>'allowed')::boolean, 'burst-dominated evidence should block';
  assert (result#>'{guard,reasons}') ? 'last_24h_burst_dominance',
    'burst reason missing';

  -- Evidence must span at least three distinct days.
  result := public.project_l_adaptive_strategy_drift_guard_v1(
    u_days,'general_recall','lexical','hybrid',
    jsonb_build_array(
      jsonb_build_object('mode','lexical','score',0.50,'served',true,'served_at',t-interval '48 hours'),
      jsonb_build_object('mode','lexical','score',0.50,'served',true,'served_at',t-interval '40 hours'),
      jsonb_build_object('mode','lexical','score',0.50,'served',true,'served_at',t-interval '32 hours'),
      jsonb_build_object('mode','lexical','score',0.50,'served',true,'served_at',t-interval '24 hours'),
      jsonb_build_object('mode','lexical','score',0.50,'served',true,'served_at',t-interval '16 hours'),
      jsonb_build_object('mode','hybrid','score',0.95,'served',true,'served_at',t-interval '47 hours'),
      jsonb_build_object('mode','hybrid','score',0.95,'served',true,'served_at',t-interval '40 hours'),
      jsonb_build_object('mode','hybrid','score',0.95,'served',true,'served_at',t-interval '32 hours'),
      jsonb_build_object('mode','hybrid','score',0.95,'served',true,'served_at',t-interval '25 hours'),
      jsonb_build_object('mode','hybrid','score',0.95,'served',true,'served_at',t-interval '24 hours')
    ),t
  );
  assert not (result->>'allowed')::boolean, 'two-day evidence should block';
  assert (result#>'{guard,reasons}') ? 'insufficient_distinct_days',
    'distinct-day reason missing';

  -- Old evidence must not be revived.
  result := public.project_l_adaptive_strategy_drift_guard_v1(
    u_stale,'general_recall','lexical','hybrid',
    jsonb_build_array(
      jsonb_build_object('mode','lexical','score',0.50,'served',true,'served_at',t-interval '24 days'),
      jsonb_build_object('mode','lexical','score',0.50,'served',true,'served_at',t-interval '22 days'),
      jsonb_build_object('mode','lexical','score',0.50,'served',true,'served_at',t-interval '20 days'),
      jsonb_build_object('mode','lexical','score',0.50,'served',true,'served_at',t-interval '18 days'),
      jsonb_build_object('mode','lexical','score',0.50,'served',true,'served_at',t-interval '16 days'),
      jsonb_build_object('mode','hybrid','score',0.95,'served',true,'served_at',t-interval '24 days'),
      jsonb_build_object('mode','hybrid','score',0.95,'served',true,'served_at',t-interval '22 days'),
      jsonb_build_object('mode','hybrid','score',0.95,'served',true,'served_at',t-interval '20 days'),
      jsonb_build_object('mode','hybrid','score',0.95,'served',true,'served_at',t-interval '18 days'),
      jsonb_build_object('mode','hybrid','score',0.95,'served',true,'served_at',t-interval '16 days')
    ),t
  );
  assert not (result->>'allowed')::boolean, 'stale evidence should block';
  assert (result#>'{guard,reasons}') ? 'stale_evidence', 'stale reason missing';

  -- A real switch creates a 72h cooldown for any different next switch.
  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,
    supporting_sample_count,distinct_evidence_days,guard_snapshot,created_at
  ) values (
    u_cooldown,'general_recall','lexical','semantic',
    5,3,'{}'::jsonb,t-interval '24 hours'
  );

  result := public.project_l_adaptive_strategy_drift_guard_v1(
    u_cooldown,'general_recall','semantic','hybrid',valid_outcomes,t
  );
  assert not (result->>'allowed')::boolean, 'cooldown should block a new switch';
  assert (result#>'{guard,reasons}') ? 'mode_switch_cooldown', 'cooldown reason missing';

  -- Direct reversal remains blocked for seven days, even after 72h.
  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,
    supporting_sample_count,distinct_evidence_days,guard_snapshot,created_at
  ) values (
    u_osc,'general_recall','hybrid','lexical',
    5,3,'{}'::jsonb,t-interval '96 hours'
  );

  result := public.project_l_adaptive_strategy_drift_guard_v1(
    u_osc,'general_recall','lexical','hybrid',valid_outcomes,t
  );
  assert not (result->>'allowed')::boolean, 'oscillation should block';
  assert (result#>'{guard,reasons}') ? 'mode_oscillation', 'oscillation reason missing';

  -- Surface remains service-role only.
  assert not has_function_privilege(
    'anon',
    'public.project_l_adaptive_strategy_drift_guard_v1(uuid,text,text,text,jsonb,timestamptz)',
    'execute'
  ), 'anon can execute Layer 293 guard';

  assert not has_function_privilege(
    'authenticated',
    'public.project_l_adaptive_strategy_drift_guard_v1(uuid,text,text,text,jsonb,timestamptz)',
    'execute'
  ), 'authenticated can execute Layer 293 guard';

  assert has_function_privilege(
    'service_role',
    'public.project_l_adaptive_strategy_drift_guard_v1(uuid,text,text,text,jsonb,timestamptz)',
    'execute'
  ), 'service_role cannot execute Layer 293 guard';
end;
$test$;

select 'Project L Layer 293 drift guard: acceptance checks passed' as result;
rollback;
