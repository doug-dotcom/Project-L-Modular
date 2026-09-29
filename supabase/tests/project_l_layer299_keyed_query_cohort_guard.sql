-- Project L Layer 299 — transactional acceptance tests
begin;

do $test$
declare
  t timestamptz := '2026-09-29 05:50:00+00';
  u uuid := '29900000-0000-4000-8000-000000000001';
  a uuid;
  exact_a1 text := repeat('1',64);
  exact_a2 text := repeat('2',64);
  exact_a3 text := repeat('3',64);
  cohort_a text := repeat('a',64);
  cohort_b text := repeat('b',64);
  cohort_c text := repeat('c',64);
  result jsonb;
  feed jsonb;
  mismatch_blocked boolean := false;
begin
  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,
    supporting_sample_count,distinct_evidence_days,
    base_average_score,learned_average_score,advantage,
    guard_snapshot,created_at
  ) values (
    u,'general_recall','lexical','semantic',
    5,3,0.60,0.80,0.20,'{}',t-interval '6 days'
  ) returning id into a;

  insert into public.project_l_retrieval_strategy_leases(
    adaptation_event_id,user_id,intent,base_mode,learned_mode,state,
    lease_started_at,lease_expires_at,created_at,updated_at
  ) values (
    a,u,'general_recall','lexical','semantic','active',
    t-interval '6 days',t+interval '12 hours',
    t-interval '6 days',t-interval '6 days'
  );

  -- Three distinct exact queries but the same lexical cohort must not look
  -- independent enough to renew.
  perform public.project_l_record_served_outcome_cohort_bound_v1(
    u,'a1-old','general_recall','semantic',exact_a1,cohort_a,
    jsonb_build_object(
      'returned_count',4,'safe_assertion_count',4,'corroborated_count',4,
      'unique_subject_count',4,'runtime_strategy_source','active_lease',
      'lease_applied',true,'explicit_mode_used',false,
      'retrieval_fallback_used',false
    ),
    t-interval '96 hours'
  );

  perform public.project_l_record_served_outcome_cohort_bound_v1(
    u,'a2-mid','general_recall','semantic',exact_a2,cohort_a,
    jsonb_build_object(
      'returned_count',4,'safe_assertion_count',4,'corroborated_count',4,
      'unique_subject_count',4,'runtime_strategy_source','active_lease',
      'lease_applied',true,'explicit_mode_used',false,
      'retrieval_fallback_used',false
    ),
    t-interval '48 hours'
  );

  perform public.project_l_record_served_outcome_cohort_bound_v1(
    u,'a3-new','general_recall','semantic',exact_a3,cohort_a,
    jsonb_build_object(
      'returned_count',4,'safe_assertion_count',4,'corroborated_count',4,
      'unique_subject_count',4,'runtime_strategy_source','active_lease',
      'lease_applied',true,'explicit_mode_used',false,
      'retrieval_fallback_used',false
    ),
    t-interval '2 hours'
  );

  feed := public.project_l_cohort_independent_served_outcome_feed_v1(
    u,'general_recall',null,64
  );

  assert jsonb_array_length(feed)=2,
    'one lexical cohort contributed more than earliest/latest evidence';

  result := public.project_l_governed_lease_evaluation_v1(
    u,'general_recall','guard-cohort-a',t
  );

  assert result->>'status'='monitoring',
    'single lexical cohort triggered renewal';
  assert (result->>'distinctExactQueries')::integer=2,
    'independent feed should expose only cohort endpoints';
  assert (result->>'distinctLexicalCohorts')::integer=1,
    'lexical cohort diversity miscounted';
  assert result->>'reason'='positive_renewal_requires_three_lexical_cohorts',
    'correlated paraphrase cohort was not blocked';

  -- Add two more lexical cohorts. With earliest/latest evidence per cohort the
  -- final feed now reaches strong, independent evidence.
  perform public.project_l_record_served_outcome_cohort_bound_v1(
    u,'b-old','general_recall','semantic',repeat('4',64),cohort_b,
    jsonb_build_object(
      'returned_count',4,'safe_assertion_count',4,'corroborated_count',4,
      'unique_subject_count',4,'runtime_strategy_source','active_lease',
      'lease_applied',true,'explicit_mode_used',false,
      'retrieval_fallback_used',false
    ),
    t-interval '70 hours'
  );

  perform public.project_l_record_served_outcome_cohort_bound_v1(
    u,'b-new','general_recall','semantic',repeat('5',64),cohort_b,
    jsonb_build_object(
      'returned_count',4,'safe_assertion_count',4,'corroborated_count',4,
      'unique_subject_count',4,'runtime_strategy_source','active_lease',
      'lease_applied',true,'explicit_mode_used',false,
      'retrieval_fallback_used',false
    ),
    t-interval '20 hours'
  );

  perform public.project_l_record_served_outcome_cohort_bound_v1(
    u,'c-one','general_recall','semantic',repeat('6',64),cohort_c,
    jsonb_build_object(
      'returned_count',4,'safe_assertion_count',4,'corroborated_count',4,
      'unique_subject_count',4,'runtime_strategy_source','active_lease',
      'lease_applied',true,'explicit_mode_used',false,
      'retrieval_fallback_used',false
    ),
    t-interval '45 hours'
  );

  result := public.project_l_governed_lease_evaluation_v1(
    u,'general_recall','guard-three-cohorts',t
  );

  assert result->>'status'='renewal_window_evaluation',
    'three lexical cohorts did not enter renewal evaluation';
  assert (result->>'distinctLexicalCohorts')::integer=3,
    'three lexical cohorts not recognised';
  assert result#>>'{leaseEvaluation,status}'='renewed',
    'healthy cohort-independent evidence did not renew';

  -- Same request replayed with a different cohort must fail closed.
  begin
    perform public.project_l_record_served_outcome_cohort_bound_v1(
      u,'a1-old','general_recall','semantic',exact_a1,cohort_b,
      jsonb_build_object(
        'returned_count',4,'runtime_strategy_source','active_lease',
        'lease_applied',true
      ),
      t
    );
  exception
    when others then
      mismatch_blocked := position(
        'PROJECT_L_LAYER299_COHORT_FINGERPRINT_MISMATCH' in sqlerrm
      ) > 0;
  end;

  assert mismatch_blocked,
    'request replay with a different lexical cohort was accepted';

  assert not has_table_privilege(
    'service_role',
    'public.project_l_retrieval_outcome_cohort_bindings',
    'update'
  ), 'service_role can mutate cohort bindings';

  assert not has_table_privilege(
    'service_role',
    'public.project_l_retrieval_outcome_cohort_bindings',
    'delete'
  ), 'service_role can delete cohort bindings';

  assert not has_function_privilege(
    'anon',
    'public.project_l_record_served_outcome_cohort_bound_v1(uuid,text,text,text,text,text,jsonb,timestamptz)',
    'execute'
  ), 'anon can bind keyed query cohorts';

  assert has_function_privilege(
    'service_role',
    'public.project_l_cohort_independent_served_outcome_feed_v1(uuid,text,timestamptz,integer)',
    'execute'
  ), 'service_role cannot read cohort-independent feed';
end;
$test$;

select 'Project L Layer 299 keyed query cohort guard: acceptance checks passed' as result;
rollback;
