-- Project L Layer 295 — transactional acceptance tests
begin;

do $test$
declare
  t timestamptz := '2026-09-29 01:00:00+00';
  u_explicit uuid := '29500000-0000-4000-8000-000000000001';
  u_active uuid := '29500000-0000-4000-8000-000000000002';
  u_clock uuid := '29500000-0000-4000-8000-000000000003';
  u_unready uuid := '29500000-0000-4000-8000-000000000004';
  u_hybrid uuid := '29500000-0000-4000-8000-000000000005';
  a uuid;
  result jsonb;
begin
  -- Explicit lexical request outranks an active semantic lease.
  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,supporting_sample_count,
    distinct_evidence_days,guard_snapshot,created_at
  ) values (
    u_explicit,'general_recall','lexical','semantic',5,3,'{}',t-interval '1 day'
  ) returning id into a;

  insert into public.project_l_retrieval_strategy_leases(
    adaptation_event_id,user_id,intent,base_mode,learned_mode,state,
    lease_started_at,lease_expires_at
  ) values (
    a,u_explicit,'general_recall','lexical','semantic','active',
    t-interval '1 day',t+interval '6 days'
  );

  result := public.project_l_runtime_retrieval_decision_v1(
    u_explicit,'general_recall','lexical','semantic',true,false,t
  );
  assert result->>'status' = 'explicit', 'explicit request not honoured';
  assert result->>'effectiveMode' = 'lexical', 'lease overrode explicit lexical choice';
  assert not (result->>'leaseApplied')::boolean, 'explicit path applied lease';

  -- Active semantic lease is enforced when semantic runtime is ready.
  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,supporting_sample_count,
    distinct_evidence_days,guard_snapshot,created_at
  ) values (
    u_active,'general_recall','lexical','semantic',5,3,'{}',t-interval '1 day'
  ) returning id into a;

  insert into public.project_l_retrieval_strategy_leases(
    adaptation_event_id,user_id,intent,base_mode,learned_mode,state,
    lease_started_at,lease_expires_at
  ) values (
    a,u_active,'general_recall','lexical','semantic','active',
    t-interval '1 day',t+interval '6 days'
  );

  result := public.project_l_runtime_retrieval_decision_v1(
    u_active,'general_recall',null,'lexical',true,false,t
  );
  assert result->>'effectiveMode' = 'semantic', 'active semantic lease not enforced';
  assert (result->>'leaseApplied')::boolean, 'active lease not reported';

  -- Clock expiry is enforced even before Layer 294 persists terminal state.
  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,supporting_sample_count,
    distinct_evidence_days,guard_snapshot,created_at
  ) values (
    u_clock,'general_recall','lexical','semantic',5,3,'{}',t-interval '8 days'
  ) returning id into a;

  insert into public.project_l_retrieval_strategy_leases(
    adaptation_event_id,user_id,intent,base_mode,learned_mode,state,
    lease_started_at,lease_expires_at
  ) values (
    a,u_clock,'general_recall','lexical','semantic','active',
    t-interval '8 days',t-interval '1 hour'
  );

  result := public.project_l_runtime_retrieval_decision_v1(
    u_clock,'general_recall',null,'semantic',true,false,t
  );
  assert result->>'effectiveMode' = 'lexical', 'clock-expired lease did not return to base';
  assert result->>'source' = 'lease_clock_expired_base', 'clock expiry source missing';

  -- Runtime readiness can block learned semantic and safely fall back to base.
  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,supporting_sample_count,
    distinct_evidence_days,guard_snapshot,created_at
  ) values (
    u_unready,'general_recall','lexical','semantic',5,3,'{}',t-interval '1 day'
  ) returning id into a;

  insert into public.project_l_retrieval_strategy_leases(
    adaptation_event_id,user_id,intent,base_mode,learned_mode,state,
    lease_started_at,lease_expires_at
  ) values (
    a,u_unready,'general_recall','lexical','semantic','active',
    t-interval '1 day',t+interval '6 days'
  );

  result := public.project_l_runtime_retrieval_decision_v1(
    u_unready,'general_recall',null,'semantic',false,false,t
  );
  assert result->>'effectiveMode' = 'lexical', 'unready semantic runtime was selected';
  assert position('desired_mode_unavailable_fallback_base' in result->>'reason') > 0,
    'runtime readiness fallback reason missing';

  -- Hybrid learning cannot leak into runtime before a real hybrid executor exists.
  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,supporting_sample_count,
    distinct_evidence_days,guard_snapshot,created_at
  ) values (
    u_hybrid,'general_recall','lexical','hybrid',5,3,'{}',t-interval '1 day'
  ) returning id into a;

  insert into public.project_l_retrieval_strategy_leases(
    adaptation_event_id,user_id,intent,base_mode,learned_mode,state,
    lease_started_at,lease_expires_at
  ) values (
    a,u_hybrid,'general_recall','lexical','hybrid','active',
    t-interval '1 day',t+interval '6 days'
  );

  result := public.project_l_runtime_retrieval_decision_v1(
    u_hybrid,'general_recall',null,'semantic',true,false,t
  );
  assert result->>'effectiveMode' = 'lexical', 'unsupported hybrid leaked into runtime';

  -- No learned state preserves the existing runtime default.
  result := public.project_l_runtime_retrieval_decision_v1(
    '29500000-0000-4000-8000-000000000099',
    'general_recall',null,'semantic',true,false,t
  );
  assert result->>'effectiveMode' = 'semantic', 'existing semantic default changed';

  assert not has_function_privilege(
    'anon',
    'public.project_l_runtime_retrieval_decision_v1(uuid,text,text,text,boolean,boolean,timestamptz)',
    'execute'
  ), 'anon can execute Layer 295 selector';

  assert not has_function_privilege(
    'authenticated',
    'public.project_l_runtime_retrieval_decision_v1(uuid,text,text,text,boolean,boolean,timestamptz)',
    'execute'
  ), 'authenticated can execute Layer 295 selector';

  assert has_function_privilege(
    'service_role',
    'public.project_l_runtime_retrieval_decision_v1(uuid,text,text,text,boolean,boolean,timestamptz)',
    'execute'
  ), 'service_role cannot execute Layer 295 selector';
end;
$test$;

select 'Project L Layer 295 runtime lease enforcement: acceptance checks passed' as result;
rollback;
