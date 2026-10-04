-- Project L Layer 294 — transactional acceptance tests
begin;

do $test$
declare
  t timestamptz := '2026-09-29 01:00:00+00';

  u_active uuid := '29400000-0000-4000-8000-000000000001';
  u_renew uuid := '29400000-0000-4000-8000-000000000002';
  u_expire uuid := '29400000-0000-4000-8000-000000000003';
  u_revoke uuid := '29400000-0000-4000-8000-000000000004';

  a_active uuid;
  a_renew uuid;
  a_expire uuid;
  a_revoke uuid;

  healthy jsonb;
  weak jsonb;
  sparse jsonb;
  result jsonb;
begin
  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,
    evidence_window_start,evidence_window_end,
    supporting_sample_count,distinct_evidence_days,evidence_span_hours,
    burst_share,base_average_score,learned_average_score,advantage,
    guard_snapshot,created_at
  ) values
    (u_active,'general_recall','lexical','hybrid',t-interval '9 days',t-interval '8 days',
      5,3,72,0.2,0.60,0.80,0.20,'{}',t-interval '2 days')
  returning id into a_active;

  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,
    evidence_window_start,evidence_window_end,
    supporting_sample_count,distinct_evidence_days,evidence_span_hours,
    burst_share,base_average_score,learned_average_score,advantage,
    guard_snapshot,created_at
  ) values
    (u_renew,'general_recall','lexical','hybrid',t-interval '12 days',t-interval '8 days',
      5,3,72,0.2,0.60,0.80,0.20,'{}',t-interval '5 days')
  returning id into a_renew;

  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,
    evidence_window_start,evidence_window_end,
    supporting_sample_count,distinct_evidence_days,evidence_span_hours,
    burst_share,base_average_score,learned_average_score,advantage,
    guard_snapshot,created_at
  ) values
    (u_expire,'general_recall','lexical','hybrid',t-interval '20 days',t-interval '15 days',
      5,3,72,0.2,0.60,0.80,0.20,'{}',t-interval '8 days')
  returning id into a_expire;

  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,
    evidence_window_start,evidence_window_end,
    supporting_sample_count,distinct_evidence_days,evidence_span_hours,
    burst_share,base_average_score,learned_average_score,advantage,
    guard_snapshot,created_at
  ) values
    (u_revoke,'general_recall','lexical','hybrid',t-interval '12 days',t-interval '8 days',
      5,3,72,0.2,0.60,0.80,0.20,'{}',t-interval '5 days')
  returning id into a_revoke;

  healthy := jsonb_build_array(
    jsonb_build_object('mode','hybrid','score',0.79,'served',true,'served_at',t-interval '96 hours'),
    jsonb_build_object('mode','hybrid','score',0.81,'served',true,'served_at',t-interval '72 hours'),
    jsonb_build_object('mode','hybrid','score',0.80,'served',true,'served_at',t-interval '50 hours'),
    jsonb_build_object('mode','hybrid','score',0.82,'served',true,'served_at',t-interval '27 hours'),
    jsonb_build_object('mode','hybrid','score',0.83,'served',true,'served_at',t-interval '2 hours')
  );

  weak := jsonb_build_array(
    jsonb_build_object('mode','hybrid','score',0.50,'served',true,'served_at',t-interval '96 hours'),
    jsonb_build_object('mode','hybrid','score',0.52,'served',true,'served_at',t-interval '72 hours'),
    jsonb_build_object('mode','hybrid','score',0.51,'served',true,'served_at',t-interval '50 hours'),
    jsonb_build_object('mode','hybrid','score',0.49,'served',true,'served_at',t-interval '27 hours'),
    jsonb_build_object('mode','hybrid','score',0.50,'served',true,'served_at',t-interval '2 hours')
  );

  sparse := jsonb_build_array(
    jsonb_build_object('mode','hybrid','score',0.82,'served',true,'served_at',t-interval '3 hours')
  );

  -- New lease remains active while it is inside its seven-day window and
  -- insufficient fresh evidence has accumulated.
  result := public.project_l_strategy_lease_status_v1(
    u_active,'general_recall',sparse,t
  );
  assert result->>'status' = 'active', 'young lease should remain active';
  assert result->>'effectiveMode' = 'hybrid', 'young lease should use learned mode';

  -- Distributed, fresh, healthy post-switch evidence renews for another week.
  result := public.project_l_strategy_lease_status_v1(
    u_renew,'general_recall',healthy,t
  );
  assert result->>'status' = 'renewed', 'healthy lease should renew';
  assert result->>'effectiveMode' = 'hybrid', 'renewed lease should keep learned mode';
  assert (result->>'renewalCount')::integer = 1, 'renewal count should increment';
  assert (
    select count(*)
    from public.project_l_retrieval_strategy_lease_events
    where adaptation_event_id=a_renew and action='renewed'
  ) = 1, 'renewal audit event missing';

  -- A lease with no sufficient fresh evidence expires to the original base mode.
  result := public.project_l_strategy_lease_status_v1(
    u_expire,'general_recall','[]'::jsonb,t
  );
  assert result->>'status' = 'expired', 'stale lease should expire';
  assert result->>'effectiveMode' = 'lexical', 'expired lease should return to base mode';

  -- Sufficient evidence that materially degraded revokes early.
  result := public.project_l_strategy_lease_status_v1(
    u_revoke,'general_recall',weak,t
  );
  assert result->>'status' = 'revoked', 'degraded lease should revoke';
  assert result->>'effectiveMode' = 'lexical', 'revoked lease should return to base mode';

  -- Terminal states cannot self-revive from later outcomes.
  result := public.project_l_strategy_lease_status_v1(
    u_revoke,'general_recall',healthy,t+interval '1 day'
  );
  assert result->>'status' = 'revoked', 'terminal lease self-revived';
  assert result->>'effectiveMode' = 'lexical', 'revoked lease changed mode';

  -- Surface remains service-role only.
  assert not has_function_privilege(
    'anon',
    'public.project_l_strategy_lease_status_v1(uuid,text,jsonb,timestamptz)',
    'execute'
  ), 'anon can execute Layer 294 lease evaluator';

  assert not has_function_privilege(
    'authenticated',
    'public.project_l_strategy_lease_status_v1(uuid,text,jsonb,timestamptz)',
    'execute'
  ), 'authenticated can execute Layer 294 lease evaluator';

  assert has_function_privilege(
    'service_role',
    'public.project_l_strategy_lease_status_v1(uuid,text,jsonb,timestamptz)',
    'execute'
  ), 'service_role cannot execute Layer 294 lease evaluator';
end;
$test$;

select 'Project L Layer 294 strategy lease: acceptance checks passed' as result;
rollback;
