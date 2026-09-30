-- Project L Memory Layer 300 — transactional acceptance tests
begin;

do $test$
declare
  t timestamptz := '2026-09-29 06:30:00+00';
  health jsonb;
  status jsonb;
  result jsonb;
begin
  -- Normalize fixture state inside the transaction.
  update public.project_l_adaptive_memory_activation
  set
    mode='shadow_only',
    generation=1,
    reason='layer300_test_shadow',
    enabled_at=null,
    updated_at=t
  where id='global';

  delete from public.project_l_adaptive_memory_activation_events;

  health := public.project_l_adaptive_memory_stack_health_v1();

  assert (health->>'stackReady')::boolean,
    'full Layers 293-299 stack was not certified healthy';
  assert jsonb_array_length(health->'missing')=0,
    'healthy stack reported missing components';

  status := public.project_l_adaptive_memory_activation_status_v1();

  assert status->>'configuredMode'='shadow_only',
    'Layer 300 did not default to shadow-only';
  assert status->>'effectiveMode'='shadow_only',
    'shadow-only config unexpectedly influenced runtime';
  assert not (status->>'runtimeInfluenceEnabled')::boolean,
    'shadow-only mode enabled adaptive runtime influence';
  assert (status->>'shadowEvaluationEnabled')::boolean,
    'shadow evaluation disabled unexpectedly';

  -- Healthy stack can be explicitly promoted from shadow_only.
  result := public.project_l_set_adaptive_memory_activation_v1(
    'active',
    'layer300 acceptance activation',
    1,
    t
  );

  assert result->>'status'='changed',
    'healthy shadow-only stack could not activate';
  assert (result->>'generation')::bigint=2,
    'activation generation did not advance';

  status := public.project_l_adaptive_memory_activation_status_v1();

  assert status->>'effectiveMode'='active',
    'active healthy config did not become effective';
  assert (status->>'runtimeInfluenceEnabled')::boolean,
    'active healthy stack did not enable runtime influence';

  -- Stale admin actions must not overwrite a newer decision.
  result := public.project_l_set_adaptive_memory_activation_v1(
    'disabled',
    'stale generation should conflict',
    1,
    t+interval '1 minute'
  );

  assert result->>'status'='conflict',
    'stale generation changed activation state';

  -- Kill switch is immediate and audited.
  result := public.project_l_set_adaptive_memory_activation_v1(
    'disabled',
    'layer300 acceptance kill switch',
    2,
    t+interval '2 minutes'
  );

  assert result->>'status'='changed',
    'kill switch did not change state';
  assert (result->>'generation')::bigint=3,
    'kill switch generation did not advance';

  status := public.project_l_adaptive_memory_activation_status_v1();

  assert status->>'effectiveMode'='disabled',
    'disabled gate was not effective';
  assert not (status->>'runtimeInfluenceEnabled')::boolean,
    'disabled gate still allowed adaptive runtime influence';

  -- ACTIVE cannot be reached directly from DISABLED.
  result := public.project_l_set_adaptive_memory_activation_v1(
    'active',
    'direct disabled to active must block',
    3,
    t+interval '3 minutes'
  );

  assert result->>'status'='blocked',
    'disabled to active transition bypassed shadow gate';
  assert result->>'reason'='activation_requires_shadow_only_prestate',
    'wrong reason for blocked direct activation';

  result := public.project_l_set_adaptive_memory_activation_v1(
    'shadow_only',
    'return through shadow before activation',
    3,
    t+interval '4 minutes'
  );
  assert (result->>'generation')::bigint=4,
    'shadow transition did not advance generation';

  result := public.project_l_set_adaptive_memory_activation_v1(
    'active',
    'reactivate after explicit shadow stage',
    4,
    t+interval '5 minutes'
  );
  assert result->>'status'='changed',
    'shadow to active transition failed';
  assert (result->>'generation')::bigint=5,
    'reactivation generation mismatch';

  assert (
    select count(*)
    from public.project_l_adaptive_memory_activation_events
  )=4, 'activation audit event count mismatch';

  assert not has_function_privilege(
    'anon',
    'public.project_l_adaptive_memory_activation_status_v1()',
    'execute'
  ), 'anon can read adaptive activation status';

  assert not has_function_privilege(
    'authenticated',
    'public.project_l_set_adaptive_memory_activation_v1(text,text,bigint,timestamptz)',
    'execute'
  ), 'authenticated can change adaptive activation state';

  assert has_function_privilege(
    'service_role',
    'public.project_l_set_adaptive_memory_activation_v1(text,text,bigint,timestamptz)',
    'execute'
  ), 'service_role cannot operate activation gate';
end;
$test$;

select 'Project L Memory Layer 300 activation gate: acceptance checks passed' as result;
rollback;
