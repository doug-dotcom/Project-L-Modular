-- Project L Memory Layer 301 — transactional acceptance tests
begin;

do $test$
declare
  t timestamptz := '2026-09-29 07:00:00+00';
  u uuid := '30100000-0000-4000-8000-000000000001';
  cert jsonb;
  status jsonb;
  result jsonb;
  i integer;
  fp text;
  cohort text;
  obs_at timestamptz;
begin
  update public.project_l_adaptive_memory_activation
  set
    mode='shadow_only',
    generation=1,
    required_layer_floor=301,
    reason='layer301 acceptance shadow',
    enabled_at=null,
    shadow_started_at=t-interval '96 hours',
    activation_basis_shadow_generation=null,
    updated_at=t-interval '96 hours'
  where id='global';

  delete from public.project_l_adaptive_memory_activation_events;
  delete from public.project_l_adaptive_memory_shadow_observations;

  -- 19 eligible observations are not enough even with adequate time/breadth.
  for i in 1..19 loop
    fp := lpad(to_hex(i),64,'0');
    cohort := repeat(substr('abcde',((i-1)%5)+1,1),64);
    obs_at := case ((i-1)%4)
      when 0 then t-interval '70 hours'
      when 1 then t-interval '50 hours'
      when 2 then t-interval '26 hours'
      else t-interval '2 hours'
    end + make_interval(mins=>i);

    result := public.project_l_record_adaptive_shadow_observation_v1(
      u,
      'shadow-'||i,
      'general_recall',
      fp,
      cohort,
      'lexical',
      case when i<=10 then 'semantic' else 'lexical' end,
      case when i<=10 then 'active_lease' else 'runtime_default' end,
      'layer301 acceptance proposal',
      false,
      obs_at
    );

    assert result->>'status'='recorded',
      'eligible shadow observation was not recorded';
  end loop;

  cert := public.project_l_adaptive_shadow_certification_v1(1,t);

  assert not (cert->>'certified')::boolean,
    '19 observations incorrectly certified burn-in';
  assert cert->'missing' ? 'shadow_observations_20',
    'missing 20-observation requirement not reported';

  result := public.project_l_set_adaptive_memory_activation_v1(
    'active',
    'activation before burn in must block',
    1,
    t
  );

  assert result->>'status'='blocked',
    'uncertified shadow activated';
  assert result->>'reason'='activation_requires_shadow_burn_in',
    'wrong reason for uncertified activation block';

  -- Observation 20 completes the current-generation certificate.
  result := public.project_l_record_adaptive_shadow_observation_v1(
    u,
    'shadow-20',
    'general_recall',
    lpad(to_hex(20),64,'0'),
    repeat('e',64),
    'lexical',
    'semantic',
    'active_lease',
    'layer301 final qualifying proposal',
    false,
    t-interval '1 hour'
  );
  assert result->>'status'='recorded',
    '20th shadow observation failed';

  cert := public.project_l_adaptive_shadow_certification_v1(1,t);

  assert (cert->>'certified')::boolean,
    'complete burn-in was not certified';
  assert (cert#>>'{observed,observationCount}')::integer=20,
    'certification observation count mismatch';
  assert (cert#>>'{observed,distinctExactQueries}')::integer>=8,
    'exact query breadth not recognised';
  assert (cert#>>'{observed,distinctLexicalCohorts}')::integer>=5,
    'cohort breadth not recognised';
  assert (cert#>>'{observed,modeChangingProposals}')::integer>=5,
    'meaningful shadow proposals not recognised';
  assert (cert#>>'{observed,modeChangingCohorts}')::integer>=3,
    'mode-changing cohort breadth not recognised';

  result := public.project_l_set_adaptive_memory_activation_v1(
    'active',
    'certified layer301 shadow activation',
    1,
    t
  );

  assert result->>'status'='changed',
    'certified shadow could not activate';
  assert (result->>'generation')::bigint=2,
    'activation generation mismatch';
  assert (result->>'activationBasisShadowGeneration')::bigint=1,
    'activation did not retain certified shadow generation';

  status := public.project_l_adaptive_memory_activation_status_v1();

  assert status->>'effectiveMode'='active',
    'certified active gate did not become effective';
  assert (status->>'runtimeInfluenceEnabled')::boolean,
    'certified active gate did not allow runtime influence';
  assert (status->>'shadowCertified')::boolean,
    'active status lost its shadow certificate';

  -- Disable -> new shadow cycle. Old generation-1 evidence must not certify it.
  result := public.project_l_set_adaptive_memory_activation_v1(
    'disabled',
    'layer301 reset burn in',
    2,
    t+interval '1 hour'
  );
  assert (result->>'generation')::bigint=3,
    'disable generation mismatch';

  result := public.project_l_set_adaptive_memory_activation_v1(
    'shadow_only',
    'layer301 begin fresh shadow',
    3,
    t+interval '2 hours'
  );
  assert (result->>'generation')::bigint=4,
    'new shadow generation mismatch';

  cert := public.project_l_adaptive_shadow_certification_v1(
    4,
    t+interval '80 hours'
  );

  assert not (cert->>'certified')::boolean,
    'old shadow observations certified a new generation';
  assert (cert#>>'{observed,observationCount}')::integer=0,
    'old generation observations leaked into new shadow cycle';

  result := public.project_l_set_adaptive_memory_activation_v1(
    'active',
    'new cycle without observations must block',
    4,
    t+interval '80 hours'
  );

  assert result->>'status'='blocked',
    'fresh uncertified shadow cycle activated';
  assert result->>'reason'='activation_requires_shadow_burn_in',
    'fresh shadow activation blocked for wrong reason';

  -- Explicit requests never count toward burn-in.
  result := public.project_l_record_adaptive_shadow_observation_v1(
    u,
    'shadow-explicit',
    'general_recall',
    repeat('f',64),
    repeat('f',64),
    'lexical',
    'semantic',
    'explicit_request',
    'explicit request ignored',
    true,
    t+interval '3 hours'
  );

  assert result->>'reason'='explicit_request_not_shadow_burn_in',
    'explicit request counted toward burn-in';

  assert not has_table_privilege(
    'service_role',
    'public.project_l_adaptive_memory_shadow_observations',
    'update'
  ), 'service_role can mutate shadow observations';

  assert not has_table_privilege(
    'service_role',
    'public.project_l_adaptive_memory_shadow_observations',
    'delete'
  ), 'service_role can delete shadow observations';

  assert not has_function_privilege(
    'anon',
    'public.project_l_record_adaptive_shadow_observation_v1(uuid,text,text,text,text,text,text,text,text,boolean,timestamptz)',
    'execute'
  ), 'anon can record shadow burn-in evidence';

  assert has_function_privilege(
    'service_role',
    'public.project_l_adaptive_shadow_certification_v1(bigint,timestamptz)',
    'execute'
  ), 'service_role cannot read shadow certification';
end;
$test$;

select 'Project L Memory Layer 301 shadow burn-in: acceptance checks passed' as result;
rollback;
