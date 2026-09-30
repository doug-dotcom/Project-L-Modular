-- Project L Memory Layer 304 — transactional acceptance tests
begin;

do $test$
declare
  t timestamptz := '2026-09-29 13:30:00+00';
  u uuid := '30400000-0000-4000-8000-000000000001';
  result jsonb;
  cert jsonb;
  i integer;
  replay_blocked boolean := false;
begin
  update public.project_l_adaptive_memory_activation
  set
    mode='shadow_only',
    generation=1,
    required_layer_floor=304,
    reason='layer304 acceptance shadow',
    shadow_started_at=t-interval '96 hours',
    activation_basis_shadow_generation=null,
    updated_at=t-interval '96 hours'
  where id='global';

  delete from public.project_l_adaptive_memory_shadow_counterfactuals;
  delete from public.project_l_adaptive_memory_counterfactual_executions;
  delete from public.project_l_adaptive_memory_counterfactual_sampling;

  -- Ten admitted reservations with ten completed quality+execution receipts.
  for i in 1..10 loop
    insert into public.project_l_adaptive_memory_counterfactual_sampling(
      user_id,request_id,activation_generation,intent,
      query_fingerprint,query_cohort_fingerprint,
      actual_mode,proposed_mode,admitted,decision_reason,utc_day,
      daily_admitted_before,cohort_daily_admitted_before,
      generation_admitted_before,quality_certified_before,observed_at
    ) values (
      u,'exec-'||i,1,'general_recall',
      lpad(to_hex(3000+i),64,'0'),
      lpad(to_hex(4000+i),64,'0'),
      'lexical','semantic',true,'counterfactual_sample_admitted',
      (t::date-(i/4)),0,0,i-1,false,t-interval '2 hours'
    );

    insert into public.project_l_adaptive_memory_shadow_counterfactuals(
      user_id,request_id,activation_generation,intent,
      query_fingerprint,query_cohort_fingerprint,
      actual_mode,proposed_mode,proposal_source,proposal_reason,
      actual_score,proposed_score,advantage,proposed_won,material_loss,
      actual_metrics,proposed_metrics,observed_at
    ) values (
      u,'exec-'||i,1,'general_recall',
      lpad(to_hex(3000+i),64,'0'),
      lpad(to_hex(4000+i),64,'0'),
      'lexical','semantic','active_lease','layer304 fixture',
      0.60,0.80,0.20,true,false,'{}','{}',t-interval '2 hours'
    );

    result := public.project_l_record_adaptive_counterfactual_execution_v1(
      u,'exec-'||i,'completed',500+i,null,t-interval '1 hour'
    );
    assert result->>'status'='recorded',
      'completed execution receipt was not recorded';
  end loop;

  cert := public.project_l_adaptive_counterfactual_reliability_v1(1,t);
  assert (cert->>'certified')::boolean,
    'ten reliable executions did not certify Layer 304';
  assert (cert#>>'{observed,completionRate}')::numeric=1,
    'completion rate should be 100 percent';
  assert (cert#>>'{observed,timeoutShare}')::numeric=0,
    'timeout share should be zero';

  -- COMPLETED without a quality receipt is rejected.
  insert into public.project_l_adaptive_memory_counterfactual_sampling(
    user_id,request_id,activation_generation,intent,
    query_fingerprint,query_cohort_fingerprint,
    actual_mode,proposed_mode,admitted,decision_reason,utc_day,
    daily_admitted_before,cohort_daily_admitted_before,
    generation_admitted_before,quality_certified_before,observed_at
  ) values (
    u,'no-quality',1,'general_recall',repeat('a',64),repeat('b',64),
    'lexical','semantic',true,'counterfactual_sample_admitted',t::date,
    0,0,10,false,t
  );

  begin
    perform public.project_l_record_adaptive_counterfactual_execution_v1(
      u,'no-quality','completed',400,null,t
    );
  exception
    when others then
      replay_blocked := position(
        'PROJECT_L_LAYER304_COMPLETED_QUALITY_RECEIPT_REQUIRED' in sqlerrm
      )>0;
  end;
  assert replay_blocked,
    'completed execution without quality evidence was accepted';

  -- Timeout is a terminal receipt and can be recorded without quality.
  result := public.project_l_record_adaptive_counterfactual_execution_v1(
    u,'no-quality','timed_out',1200,'shadow_counterfactual_deadline',t
  );
  assert result->>'terminalStatus'='timed_out',
    'timeout receipt was not recorded';

  -- A duplicate terminal status is idempotent; changing it fails closed.
  result := public.project_l_record_adaptive_counterfactual_execution_v1(
    u,'no-quality','timed_out',1200,'shadow_counterfactual_deadline',t
  );
  assert result->>'status'='already_recorded',
    'duplicate timeout receipt was not idempotent';

  replay_blocked := false;
  begin
    perform public.project_l_record_adaptive_counterfactual_execution_v1(
      u,'no-quality','failed',1200,'changed_status',t
    );
  exception
    when others then
      replay_blocked := position(
        'PROJECT_L_LAYER304_EXECUTION_REPLAY_MISMATCH' in sqlerrm
      )>0;
  end;
  assert replay_blocked,
    'execution terminal status replay mismatch was accepted';

  assert not has_table_privilege(
    'service_role',
    'public.project_l_adaptive_memory_counterfactual_executions',
    'update'
  ), 'service_role can update counterfactual execution receipts';

  assert not has_table_privilege(
    'service_role',
    'public.project_l_adaptive_memory_counterfactual_executions',
    'delete'
  ), 'service_role can delete counterfactual execution receipts';

  assert not has_function_privilege(
    'anon',
    'public.project_l_record_adaptive_counterfactual_execution_v1(uuid,text,text,numeric,text,timestamptz)',
    'execute'
  ), 'anon can record execution receipts';

  assert has_function_privilege(
    'service_role',
    'public.project_l_adaptive_counterfactual_reliability_v1(bigint,timestamptz)',
    'execute'
  ), 'service_role cannot read reliability certificate';
end;
$test$;

select 'Project L Memory Layer 304 background isolation: acceptance checks passed' as result;
rollback;
