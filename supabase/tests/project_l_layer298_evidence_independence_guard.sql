-- Project L Layer 298 — transactional acceptance tests
begin;

do $test$
declare
  t timestamptz := '2026-09-29 03:40:00+00';
  u uuid := '29800000-0000-4000-8000-000000000001';
  a uuid;
  fp_a text := repeat('a',64);
  fp_b text := repeat('b',64);
  fp_c text := repeat('c',64);
  result jsonb;
  feed jsonb;
  i integer;
  served_time timestamptz;
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

  -- Five repeats of one normalized query are five served requests but only
  -- two independent evidence points: earliest + latest.
  for i in 1..5 loop
    served_time := case i
      when 1 then t-interval '96 hours'
      when 2 then t-interval '72 hours'
      when 3 then t-interval '50 hours'
      when 4 then t-interval '27 hours'
      else t-interval '2 hours'
    end;

    perform public.project_l_record_served_outcome_bound_v1(
      u,'repeat-'||i,'general_recall','semantic',fp_a,
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

  feed := public.project_l_independent_served_outcome_feed_v1(
    u,'general_recall',null,64
  );

  assert jsonb_array_length(feed)=2,
    'repeated query contributed more than earliest/latest evidence';

  result := public.project_l_governed_lease_evaluation_v1(
    u,'general_recall','guard-repeat',t
  );

  assert result->>'status'='monitoring',
    'single repeated query triggered renewal evaluation';
  assert (result->>'distinctQueryFingerprints')::integer=1,
    'query fingerprint diversity miscounted';
  assert result->>'reason'='positive_renewal_requires_three_query_fingerprints',
    'single-query renewal was not blocked by independence guard';

  -- Add two genuinely distinct normalized query cohorts. The independent feed
  -- now has >=5 outcomes across >=3 fingerprints and may renew in final 24h.
  perform public.project_l_record_served_outcome_bound_v1(
    u,'b-old','general_recall','semantic',fp_b,
    jsonb_build_object(
      'returned_count',4,'safe_assertion_count',4,'corroborated_count',4,
      'unique_subject_count',4,'runtime_strategy_source','active_lease',
      'lease_applied',true,'explicit_mode_used',false,
      'retrieval_fallback_used',false
    ),
    t-interval '70 hours'
  );

  perform public.project_l_record_served_outcome_bound_v1(
    u,'b-new','general_recall','semantic',fp_b,
    jsonb_build_object(
      'returned_count',4,'safe_assertion_count',4,'corroborated_count',4,
      'unique_subject_count',4,'runtime_strategy_source','active_lease',
      'lease_applied',true,'explicit_mode_used',false,
      'retrieval_fallback_used',false
    ),
    t-interval '20 hours'
  );

  perform public.project_l_record_served_outcome_bound_v1(
    u,'c-one','general_recall','semantic',fp_c,
    jsonb_build_object(
      'returned_count',4,'safe_assertion_count',4,'corroborated_count',4,
      'unique_subject_count',4,'runtime_strategy_source','active_lease',
      'lease_applied',true,'explicit_mode_used',false,
      'retrieval_fallback_used',false
    ),
    t-interval '45 hours'
  );

  result := public.project_l_governed_lease_evaluation_v1(
    u,'general_recall','guard-diverse',t
  );

  assert result->>'status'='renewal_window_evaluation',
    'independent query evidence did not enter renewal evaluation';
  assert (result->>'distinctQueryFingerprints')::integer=3,
    'three independent query cohorts not recognised';
  assert result#>>'{leaseEvaluation,status}'='renewed',
    'independent healthy evidence did not renew';

  -- Replaying a request ID with a different query fingerprint must fail closed.
  begin
    perform public.project_l_record_served_outcome_bound_v1(
      u,'repeat-1','general_recall','semantic',fp_b,
      jsonb_build_object(
        'returned_count',4,'runtime_strategy_source','active_lease',
        'lease_applied',true
      ),
      t
    );
  exception
    when others then
      mismatch_blocked := position(
        'PROJECT_L_LAYER298_FINGERPRINT_MISMATCH' in sqlerrm
      ) > 0;
  end;

  assert mismatch_blocked,
    'request replay with a different query fingerprint was accepted';

  assert not has_table_privilege(
    'service_role',
    'public.project_l_retrieval_outcome_query_bindings',
    'update'
  ), 'service_role can mutate query bindings';

  assert not has_table_privilege(
    'service_role',
    'public.project_l_retrieval_outcome_query_bindings',
    'delete'
  ), 'service_role can delete query bindings';

  assert not has_function_privilege(
    'anon',
    'public.project_l_record_served_outcome_bound_v1(uuid,text,text,text,text,jsonb,timestamptz)',
    'execute'
  ), 'anon can bind served outcomes';

  assert has_function_privilege(
    'service_role',
    'public.project_l_independent_served_outcome_feed_v1(uuid,text,timestamptz,integer)',
    'execute'
  ), 'service_role cannot read independent outcome feed';
end;
$test$;

select 'Project L Layer 298 evidence independence: acceptance checks passed' as result;
rollback;
