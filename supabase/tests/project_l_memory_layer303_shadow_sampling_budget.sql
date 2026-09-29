-- Project L Memory Layer 303 — transactional acceptance tests
begin;

do $test$
declare
  t timestamptz := '2026-09-29 08:30:00+00';
  u uuid := '30300000-0000-4000-8000-000000000001';
  result jsonb;
  i integer;
  replay_blocked boolean := false;
begin
  update public.project_l_adaptive_memory_activation
  set
    mode='shadow_only',
    generation=1,
    required_layer_floor=303,
    reason='layer303 acceptance shadow',
    enabled_at=null,
    shadow_started_at=t-interval '96 hours',
    activation_basis_shadow_generation=null,
    updated_at=t-interval '96 hours'
  where id='global';

  delete from public.project_l_adaptive_memory_shadow_counterfactuals;
  delete from public.project_l_adaptive_memory_counterfactual_sampling;

  -- One lexical cohort gets at most one reservation per UTC day.
  result := public.project_l_adaptive_counterfactual_sample_admission_v1(
    u,'sample-a1','general_recall',repeat('1',64),repeat('a',64),
    'lexical','semantic',false,t
  );
  assert (result->>'admitted')::boolean,
    'first cohort sample was not admitted';

  result := public.project_l_adaptive_counterfactual_sample_admission_v1(
    u,'sample-a2','general_recall',repeat('2',64),repeat('a',64),
    'lexical','semantic',false,t+interval '1 minute'
  );
  assert not (result->>'admitted')::boolean,
    'second same-cohort sample was admitted on same day';
  assert result->>'reason'='cohort_daily_budget_exhausted',
    'wrong reason for same-cohort denial';

  -- Three more distinct cohorts fill the daily budget of four.
  for i in 1..3 loop
    result := public.project_l_adaptive_counterfactual_sample_admission_v1(
      u,
      'sample-extra-'||i,
      'general_recall',
      lpad(to_hex(10+i),64,'0'),
      repeat(substr('bcd',i,1),64),
      'lexical',
      'semantic',
      false,
      t+make_interval(mins=>10+i)
    );
    assert (result->>'admitted')::boolean,
      'distinct cohort failed before daily budget filled';
  end loop;

  result := public.project_l_adaptive_counterfactual_sample_admission_v1(
    u,'sample-fifth','general_recall',repeat('9',64),repeat('e',64),
    'lexical','semantic',false,t+interval '1 hour'
  );
  assert not (result->>'admitted')::boolean,
    'fifth daily counterfactual was admitted';
  assert result->>'reason'='daily_budget_exhausted',
    'wrong reason for fifth daily denial';

  -- Idempotent retry returns the original decision and cannot consume more.
  result := public.project_l_adaptive_counterfactual_sample_admission_v1(
    u,'sample-a1','general_recall',repeat('1',64),repeat('a',64),
    'lexical','semantic',false,t+interval '2 hours'
  );
  assert result->>'status'='already_decided',
    'sample admission retry was not idempotent';
  assert (result->>'admitted')::boolean,
    'idempotent retry changed the original admission';

  -- Rebinding the same request to a different cohort fails closed.
  begin
    perform public.project_l_adaptive_counterfactual_sample_admission_v1(
      u,'sample-a1','general_recall',repeat('1',64),repeat('f',64),
      'lexical','semantic',false,t+interval '3 hours'
    );
  exception
    when others then
      replay_blocked := position(
        'PROJECT_L_LAYER303_SAMPLING_REPLAY_MISMATCH' in sqlerrm
      )>0;
  end;
  assert replay_blocked,
    'sampling replay mismatch was accepted';

  -- Seed a generation-level ceiling and verify it stops further reservations.
  delete from public.project_l_adaptive_memory_counterfactual_sampling;

  for i in 1..28 loop
    insert into public.project_l_adaptive_memory_counterfactual_sampling(
      user_id,request_id,activation_generation,intent,
      query_fingerprint,query_cohort_fingerprint,
      actual_mode,proposed_mode,admitted,decision_reason,utc_day,
      daily_admitted_before,cohort_daily_admitted_before,
      generation_admitted_before,quality_certified_before,observed_at
    )
    values (
      u,'seed-'||i,1,'general_recall',
      lpad(to_hex(100+i),64,'0'),
      lpad(to_hex(500+i),64,'0'),
      'lexical','semantic',true,'counterfactual_sample_admitted',
      (t::date-(i/4)),
      0,0,i-1,false,
      t-make_interval(days=>i/4)
    );
  end loop;

  result := public.project_l_adaptive_counterfactual_sample_admission_v1(
    u,'sample-29','general_recall',repeat('8',64),repeat('7',64),
    'lexical','semantic',false,t+interval '1 day'
  );
  assert not (result->>'admitted')::boolean,
    '29th generation sample was admitted';
  assert result->>'reason'='generation_budget_exhausted',
    'wrong reason for generation budget denial';

  -- Explicit and no-op requests never enter the budget.
  result := public.project_l_adaptive_counterfactual_sample_admission_v1(
    u,'explicit','general_recall',repeat('6',64),repeat('6',64),
    'lexical','semantic',true,t
  );
  assert result->>'reason'='explicit_request_not_sampling_candidate',
    'explicit request entered sampling';

  result := public.project_l_adaptive_counterfactual_sample_admission_v1(
    u,'same-mode','general_recall',repeat('5',64),repeat('5',64),
    'lexical','lexical',false,t
  );
  assert result->>'reason'='sampling_requires_mode_change',
    'same-mode proposal entered sampling';

  assert not has_table_privilege(
    'service_role',
    'public.project_l_adaptive_memory_counterfactual_sampling',
    'update'
  ), 'service_role can update sampling reservations';

  assert not has_table_privilege(
    'service_role',
    'public.project_l_adaptive_memory_counterfactual_sampling',
    'delete'
  ), 'service_role can delete sampling reservations';

  assert not has_function_privilege(
    'anon',
    'public.project_l_adaptive_counterfactual_sample_admission_v1(uuid,text,text,text,text,text,text,boolean,timestamptz)',
    'execute'
  ), 'anon can request counterfactual sample admission';

  assert has_function_privilege(
    'service_role',
    'public.project_l_adaptive_counterfactual_sampling_status_v1(bigint,timestamptz)',
    'execute'
  ), 'service_role cannot inspect sampling budget';
end;
$test$;

select 'Project L Memory Layer 303 sampling budget: acceptance checks passed' as result;
rollback;
