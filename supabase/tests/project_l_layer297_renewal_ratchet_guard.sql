-- Project L Layer 297 — transactional acceptance tests
begin;

do $test$
declare
  t timestamptz := '2026-09-29 02:30:00+00';
  u_early uuid := '29700000-0000-4000-8000-000000000001';
  u_bad uuid := '29700000-0000-4000-8000-000000000002';
  u_window uuid := '29700000-0000-4000-8000-000000000003';
  u_expire uuid := '29700000-0000-4000-8000-000000000004';
  a uuid;
  prior_expiry timestamptz;
  result jsonb;
  i integer;
  served_time timestamptz;
begin
  -- Helper pattern: five distributed outcomes for each owner.
  -- EARLY HEALTHY: must monitor without extending expiry.
  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,
    supporting_sample_count,distinct_evidence_days,
    base_average_score,learned_average_score,advantage,
    guard_snapshot,created_at
  ) values (
    u_early,'general_recall','lexical','semantic',
    5,3,0.60,0.80,0.20,'{}',t-interval '3 days'
  ) returning id into a;

  prior_expiry := t+interval '4 days';

  insert into public.project_l_retrieval_strategy_leases(
    adaptation_event_id,user_id,intent,base_mode,learned_mode,state,
    lease_started_at,lease_expires_at,created_at,updated_at
  ) values (
    a,u_early,'general_recall','lexical','semantic','active',
    t-interval '3 days',prior_expiry,t-interval '3 days',t-interval '3 days'
  );

  for i in 1..5 loop
    served_time := case i
      when 1 then t-interval '70 hours'
      when 2 then t-interval '55 hours'
      when 3 then t-interval '48 hours'
      when 4 then t-interval '26 hours'
      else t-interval '2 hours'
    end;

    perform public.project_l_record_served_outcome_v1(
      u_early,'early-'||i,'general_recall','semantic',
      jsonb_build_object(
        'returned_count',4,
        'safe_assertion_count',4,
        'corroborated_count',4,
        'needs_corroboration_count',0,
        'unique_subject_count',4,
        'runtime_strategy_source','active_lease',
        'lease_applied',true,
        'explicit_mode_used',false,
        'retrieval_fallback_used',false
      ),
      served_time
    );
  end loop;

  result := public.project_l_governed_lease_evaluation_v1(
    u_early,'general_recall','guard-early',t
  );

  assert result->>'status'='monitoring',
    'healthy evidence renewed before final 24h';
  assert not (result->>'mutationPerformed')::boolean,
    'early healthy evaluation mutated lease';
  assert (
    select lease_expires_at
    from public.project_l_retrieval_strategy_leases
    where user_id=u_early and intent='general_recall'
  )=prior_expiry, 'early healthy evidence ratcheted lease expiry';

  -- EARLY BAD: strong degrading evidence may revoke before renewal window.
  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,
    supporting_sample_count,distinct_evidence_days,
    base_average_score,learned_average_score,advantage,
    guard_snapshot,created_at
  ) values (
    u_bad,'general_recall','lexical','semantic',
    5,3,0.60,0.80,0.20,'{}',t-interval '3 days'
  ) returning id into a;

  insert into public.project_l_retrieval_strategy_leases(
    adaptation_event_id,user_id,intent,base_mode,learned_mode,state,
    lease_started_at,lease_expires_at,created_at,updated_at
  ) values (
    a,u_bad,'general_recall','lexical','semantic','active',
    t-interval '3 days',t+interval '4 days',t-interval '3 days',t-interval '3 days'
  );

  for i in 1..5 loop
    served_time := case i
      when 1 then t-interval '70 hours'
      when 2 then t-interval '55 hours'
      when 3 then t-interval '48 hours'
      when 4 then t-interval '26 hours'
      else t-interval '2 hours'
    end;

    perform public.project_l_record_served_outcome_v1(
      u_bad,'bad-'||i,'general_recall','semantic',
      jsonb_build_object(
        'returned_count',4,
        'safe_assertion_count',0,
        'corroborated_count',0,
        'needs_corroboration_count',4,
        'unique_subject_count',1,
        'diversity_fallback_used',true,
        'runtime_strategy_source','active_lease',
        'lease_applied',true,
        'explicit_mode_used',false,
        'retrieval_fallback_used',false
      ),
      served_time
    );
  end loop;

  result := public.project_l_governed_lease_evaluation_v1(
    u_bad,'general_recall','guard-bad',t
  );

  assert result->>'status'='early_quality_review',
    'degrading evidence did not enter early review';
  assert result#>>'{leaseEvaluation,status}'='revoked',
    'degrading evidence did not revoke learned strategy';

  -- FINAL 24H HEALTHY: renewal is now allowed.
  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,
    supporting_sample_count,distinct_evidence_days,
    base_average_score,learned_average_score,advantage,
    guard_snapshot,created_at
  ) values (
    u_window,'general_recall','lexical','semantic',
    5,3,0.60,0.80,0.20,'{}',t-interval '6 days'
  ) returning id into a;

  insert into public.project_l_retrieval_strategy_leases(
    adaptation_event_id,user_id,intent,base_mode,learned_mode,state,
    lease_started_at,lease_expires_at,created_at,updated_at
  ) values (
    a,u_window,'general_recall','lexical','semantic','active',
    t-interval '6 days',t+interval '12 hours',t-interval '6 days',t-interval '6 days'
  );

  for i in 1..5 loop
    served_time := case i
      when 1 then t-interval '96 hours'
      when 2 then t-interval '72 hours'
      when 3 then t-interval '50 hours'
      when 4 then t-interval '27 hours'
      else t-interval '2 hours'
    end;

    perform public.project_l_record_served_outcome_v1(
      u_window,'window-'||i,'general_recall','semantic',
      jsonb_build_object(
        'returned_count',4,
        'safe_assertion_count',4,
        'corroborated_count',4,
        'needs_corroboration_count',0,
        'unique_subject_count',4,
        'runtime_strategy_source','active_lease',
        'lease_applied',true,
        'explicit_mode_used',false,
        'retrieval_fallback_used',false
      ),
      served_time
    );
  end loop;

  result := public.project_l_governed_lease_evaluation_v1(
    u_window,'general_recall','guard-window',t
  );

  assert result->>'status'='renewal_window_evaluation',
    'final 24h did not open renewal evaluation';
  assert result#>>'{leaseEvaluation,status}'='renewed',
    'healthy final-window evidence did not renew';

  -- CLOCK EXPIRED + INSUFFICIENT: Layer 294 must expire to base.
  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,
    supporting_sample_count,distinct_evidence_days,
    base_average_score,learned_average_score,advantage,
    guard_snapshot,created_at
  ) values (
    u_expire,'general_recall','lexical','semantic',
    5,3,0.60,0.80,0.20,'{}',t-interval '8 days'
  ) returning id into a;

  insert into public.project_l_retrieval_strategy_leases(
    adaptation_event_id,user_id,intent,base_mode,learned_mode,state,
    lease_started_at,lease_expires_at,created_at,updated_at
  ) values (
    a,u_expire,'general_recall','lexical','semantic','active',
    t-interval '8 days',t-interval '1 hour',t-interval '8 days',t-interval '8 days'
  );

  result := public.project_l_governed_lease_evaluation_v1(
    u_expire,'general_recall','guard-expire',t
  );

  assert result#>>'{leaseEvaluation,status}'='expired',
    'expired insufficient lease did not fail back';

  assert not has_function_privilege(
    'anon',
    'public.project_l_governed_lease_evaluation_v1(uuid,text,text,timestamptz)',
    'execute'
  ), 'anon can execute Layer 297 guard';

  assert not has_function_privilege(
    'authenticated',
    'public.project_l_governed_lease_evaluation_v1(uuid,text,text,timestamptz)',
    'execute'
  ), 'authenticated can execute Layer 297 guard';

  assert has_function_privilege(
    'service_role',
    'public.project_l_governed_lease_evaluation_v1(uuid,text,text,timestamptz)',
    'execute'
  ), 'service_role cannot execute Layer 297 guard';
end;
$test$;

select 'Project L Layer 297 renewal ratchet guard: acceptance checks passed' as result;
rollback;
