-- Project L Layer 296 — transactional acceptance tests
begin;

do $test$
declare
  t timestamptz := '2026-09-29 02:30:00+00';
  u uuid := '29600000-0000-4000-8000-000000000001';
  a uuid;
  result jsonb;
  feed jsonb;
  i integer;
  served_time timestamptz;
begin
  insert into public.project_l_retrieval_adaptation_events(
    user_id,intent,base_mode,learned_mode,
    evidence_window_start,evidence_window_end,
    supporting_sample_count,distinct_evidence_days,evidence_span_hours,
    burst_share,base_average_score,learned_average_score,advantage,
    guard_snapshot,created_at
  ) values (
    u,'general_recall','lexical','semantic',
    t-interval '8 days',t-interval '6 days',
    5,3,72,0.2,0.60,0.80,0.20,'{}',t-interval '5 days'
  ) returning id into a;

  insert into public.project_l_retrieval_strategy_leases(
    adaptation_event_id,user_id,intent,base_mode,learned_mode,state,
    lease_started_at,lease_expires_at,created_at,updated_at
  ) values (
    a,u,'general_recall','lexical','semantic','active',
    t-interval '5 days',t+interval '2 days',t-interval '5 days',t-interval '5 days'
  );

  -- Record five healthy outcomes actually served by the active learned lease.
  for i in 1..5 loop
    served_time := case i
      when 1 then t-interval '96 hours'
      when 2 then t-interval '72 hours'
      when 3 then t-interval '50 hours'
      when 4 then t-interval '27 hours'
      else t-interval '2 hours'
    end;

    result := public.project_l_record_served_outcome_v1(
      u,
      'req-'||i,
      'general_recall',
      'semantic',
      jsonb_build_object(
        'returned_count',4,
        'safe_assertion_count',4,
        'corroborated_count',4,
        'needs_corroboration_count',0,
        'unique_domain_count',3,
        'unique_subject_count',4,
        'diversity_fallback_used',false,
        'retrieval_fallback_used',false,
        'cache_hit',false,
        'runtime_strategy_source','active_lease',
        'runtime_strategy_reason','layer294_active_lease',
        'lease_applied',true,
        'explicit_mode_used',false
      ),
      served_time
    );

    assert result->>'status'='recorded', 'healthy outcome was not recorded';
    assert (result->>'renewalEligible')::boolean, 'active lease outcome not renewal eligible';
    assert not (result->>'adaptationEligible')::boolean,
      'self telemetry became adaptation eligible';
    assert (result->>'qualityScore')::numeric >= 0.80,
      'healthy deterministic score unexpectedly low';
  end loop;

  -- Idempotency: the same request cannot create a second evidence row.
  result := public.project_l_record_served_outcome_v1(
    u,'req-1','general_recall','semantic',
    jsonb_build_object(
      'returned_count',1,
      'runtime_strategy_source','runtime_default'
    ),
    t
  );
  assert result->>'status'='already_recorded', 'request idempotency failed';
  assert (
    select count(*) from public.project_l_retrieval_served_outcomes
    where user_id=u and request_id='req-1'
  )=1, 'duplicate served outcome row created';

  -- Explicit and fallback paths are recorded but cannot renew a learned lease.
  result := public.project_l_record_served_outcome_v1(
    u,'req-explicit','general_recall','semantic',
    jsonb_build_object(
      'returned_count',4,
      'safe_assertion_count',4,
      'corroborated_count',4,
      'unique_subject_count',4,
      'runtime_strategy_source','explicit_request',
      'lease_applied',false,
      'explicit_mode_used',true
    ),
    t-interval '1 hour'
  );
  assert not (result->>'renewalEligible')::boolean,
    'explicit override incorrectly counted for renewal';

  result := public.project_l_record_served_outcome_v1(
    u,'req-fallback','general_recall','semantic',
    jsonb_build_object(
      'returned_count',4,
      'safe_assertion_count',4,
      'corroborated_count',4,
      'unique_subject_count',4,
      'runtime_strategy_source','active_lease',
      'lease_applied',true,
      'retrieval_fallback_used',true
    ),
    t-interval '30 minutes'
  );
  assert not (result->>'renewalEligible')::boolean,
    'runtime fallback incorrectly counted for renewal';

  feed := public.project_l_served_outcome_feed_v1(
    u,'general_recall','renewal',null,64
  );
  assert jsonb_array_length(feed)=5,
    'renewal feed included ineligible outcomes';

  assert jsonb_array_length(
    public.project_l_served_outcome_feed_v1(
      u,'general_recall','adaptation',null,64
    )
  )=0, 'proxy self telemetry leaked into adaptation feed';

  -- Full Layer 296 -> 294 bridge should renew the active lease.
  result := public.project_l_auto_renewal_feed_v1(
    u,'general_recall',t
  );
  assert result#>>'{leaseEvaluation,status}'='renewed',
    'eligible real served outcomes did not renew lease';
  assert (result->>'outcomesCount')::integer=5,
    'automatic renewal feed count mismatch';

  -- Append-only/security boundary.
  assert not has_table_privilege(
    'service_role',
    'public.project_l_retrieval_served_outcomes',
    'update'
  ), 'service_role can update append-only outcome evidence';

  assert not has_table_privilege(
    'service_role',
    'public.project_l_retrieval_served_outcomes',
    'delete'
  ), 'service_role can delete append-only outcome evidence';

  assert not has_function_privilege(
    'anon',
    'public.project_l_record_served_outcome_v1(uuid,text,text,text,jsonb,timestamptz)',
    'execute'
  ), 'anon can record served outcomes';

  assert not has_function_privilege(
    'authenticated',
    'public.project_l_auto_renewal_feed_v1(uuid,text,timestamptz)',
    'execute'
  ), 'authenticated can trigger renewal feed';

  assert has_function_privilege(
    'service_role',
    'public.project_l_auto_renewal_feed_v1(uuid,text,timestamptz)',
    'execute'
  ), 'service_role cannot trigger renewal feed';
end;
$test$;

select 'Project L Layer 296 served outcome feed: acceptance checks passed' as result;
rollback;
