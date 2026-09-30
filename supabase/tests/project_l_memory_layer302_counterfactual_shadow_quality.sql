-- Project L Memory Layer 302 — transactional acceptance tests
begin;

do $test$
declare
  t timestamptz := '2026-09-29 07:00:00+00';
  u uuid := '30200000-0000-4000-8000-000000000001';
  cert jsonb;
  result jsonb;
  status jsonb;
  i integer;
  fp text;
  cohort text;
  obs_at timestamptz;
  actual_metrics jsonb := jsonb_build_object(
    'returned_count',4,
    'safe_assertion_count',2,
    'corroborated_count',1,
    'needs_corroboration_count',1,
    'unique_subject_count',2,
    'diversity_fallback_used',false,
    'retrieval_fallback_used',false
  );
  proposed_metrics jsonb := jsonb_build_object(
    'returned_count',4,
    'safe_assertion_count',4,
    'corroborated_count',4,
    'needs_corroboration_count',0,
    'unique_subject_count',4,
    'diversity_fallback_used',false,
    'retrieval_fallback_used',false
  );
  replay_blocked boolean := false;
begin
  update public.project_l_adaptive_memory_activation
  set
    mode='shadow_only',
    generation=1,
    required_layer_floor=302,
    reason='layer302 acceptance shadow',
    enabled_at=null,
    shadow_started_at=t-interval '96 hours',
    activation_basis_shadow_generation=null,
    updated_at=t-interval '96 hours'
  where id='global';

  delete from public.project_l_adaptive_memory_activation_events;
  delete from public.project_l_adaptive_memory_shadow_counterfactuals;
  delete from public.project_l_adaptive_memory_shadow_observations;

  -- Satisfy Layer 301 burn-in directly with content-free synthetic fixtures.
  for i in 1..20 loop
    insert into public.project_l_adaptive_memory_shadow_observations(
      user_id,request_id,activation_generation,intent,
      query_fingerprint,query_cohort_fingerprint,
      actual_mode,proposed_mode,proposal_source,proposal_reason,
      proposal_would_change,observed_at
    )
    values (
      u,
      'burn-'||i,
      1,
      'general_recall',
      lpad(to_hex(1000+i),64,'0'),
      repeat(substr('abcde',((i-1)%5)+1,1),64),
      'lexical',
      case when i<=10 then 'semantic' else 'lexical' end,
      case when i<=10 then 'active_lease' else 'runtime_default' end,
      'layer302 burn-in fixture',
      i<=10,
      case ((i-1)%4)
        when 0 then t-interval '70 hours'
        when 1 then t-interval '50 hours'
        when 2 then t-interval '26 hours'
        else t-interval '2 hours'
      end + make_interval(mins=>i)
    );
  end loop;

  assert (
    public.project_l_adaptive_shadow_certification_v1(1,t)->>'certified'
  )::boolean, 'Layer 301 burn-in fixture did not certify';

  -- Nine strong counterfactual wins are still insufficient.
  for i in 1..9 loop
    fp := lpad(to_hex(2000+i),64,'0');
    cohort := repeat(substr('abcd',((i-1)%4)+1,1),64);
    obs_at := case ((i-1)%4)
      when 0 then t-interval '70 hours'
      when 1 then t-interval '50 hours'
      when 2 then t-interval '26 hours'
      else t-interval '2 hours'
    end + make_interval(mins=>i);

    result := public.project_l_record_adaptive_shadow_counterfactual_v1(
      u,
      'cf-'||i,
      'general_recall',
      fp,
      cohort,
      'lexical',
      'semantic',
      'active_lease',
      'layer302 acceptance proposal',
      actual_metrics,
      proposed_metrics,
      false,
      obs_at
    );

    assert result->>'status'='recorded',
      'eligible counterfactual comparison was not recorded';
    assert (result->>'proposedWon')::boolean,
      'healthy proposed path did not beat served path';
    assert (result->>'advantage')::numeric>=0.08,
      'expected counterfactual advantage was too small';
  end loop;

  cert := public.project_l_adaptive_counterfactual_certification_v1(1,t);

  assert not (cert->>'certified')::boolean,
    'nine counterfactuals incorrectly certified quality';
  assert cert->'missing' ? 'counterfactual_comparisons_10',
    'missing ten-comparison requirement not reported';

  result := public.project_l_set_adaptive_memory_activation_v1(
    'active',
    'counterfactual quality not ready',
    1,
    t
  );

  assert result->>'status'='blocked',
    'uncertified counterfactual quality activated';
  assert result->>'reason'='activation_requires_counterfactual_shadow_quality',
    'wrong activation block reason for Layer 302';

  result := public.project_l_record_adaptive_shadow_counterfactual_v1(
    u,
    'cf-10',
    'general_recall',
    lpad(to_hex(2010),64,'0'),
    repeat('d',64),
    'lexical',
    'semantic',
    'active_lease',
    'layer302 tenth proposal',
    actual_metrics,
    proposed_metrics,
    false,
    t-interval '1 hour'
  );

  assert result->>'status'='recorded',
    'tenth counterfactual comparison failed';

  cert := public.project_l_adaptive_counterfactual_certification_v1(1,t);

  assert (cert->>'certified')::boolean,
    'complete Layer 302 counterfactual evidence did not certify';
  assert (cert#>>'{observed,comparisons}')::integer=10,
    'counterfactual comparison count mismatch';
  assert (cert#>>'{observed,winRate}')::numeric>=0.70,
    'counterfactual win rate requirement failed';
  assert (cert#>>'{observed,meanAdvantage}')::numeric>=0.08,
    'counterfactual mean advantage requirement failed';
  assert (cert#>>'{observed,proposedAverageScore}')::numeric>=0.65,
    'counterfactual proposed average requirement failed';

  result := public.project_l_set_adaptive_memory_activation_v1(
    'active',
    'layer302 certified activation',
    1,
    t
  );

  assert result->>'status'='changed',
    'fully certified Layer 302 shadow could not activate';
  assert (result->>'generation')::bigint=2,
    'Layer 302 activation generation mismatch';

  status := public.project_l_adaptive_memory_activation_status_v1();

  assert status->>'effectiveMode'='active',
    'fully certified Layer 302 active gate was not effective';
  assert (status->>'counterfactualCertified')::boolean,
    'active status lost counterfactual quality certificate';

  -- Replay with changed metrics must fail closed.
  begin
    perform public.project_l_record_adaptive_shadow_counterfactual_v1(
      u,
      'cf-10',
      'general_recall',
      lpad(to_hex(2010),64,'0'),
      repeat('d',64),
      'lexical',
      'semantic',
      'active_lease',
      'replay mismatch',
      proposed_metrics,
      actual_metrics,
      false,
      t-interval '1 hour'
    );
  exception
    when others then
      replay_blocked := position(
        'PROJECT_L_LAYER302_COUNTERFACTUAL_REPLAY_MISMATCH' in sqlerrm
      )>0;
  end;

  assert replay_blocked,
    'counterfactual replay with changed scores was accepted';

  assert not has_table_privilege(
    'service_role',
    'public.project_l_adaptive_memory_shadow_counterfactuals',
    'update'
  ), 'service_role can mutate counterfactual observations';

  assert not has_table_privilege(
    'service_role',
    'public.project_l_adaptive_memory_shadow_counterfactuals',
    'delete'
  ), 'service_role can delete counterfactual observations';

  assert not has_function_privilege(
    'anon',
    'public.project_l_record_adaptive_shadow_counterfactual_v1(uuid,text,text,text,text,text,text,text,text,jsonb,jsonb,boolean,timestamptz)',
    'execute'
  ), 'anon can record adaptive counterfactual evidence';

  assert has_function_privilege(
    'service_role',
    'public.project_l_adaptive_counterfactual_certification_v1(bigint,timestamptz)',
    'execute'
  ), 'service_role cannot read counterfactual certification';
end;
$test$;

select 'Project L Memory Layer 302 counterfactual quality: acceptance checks passed' as result;
rollback;
