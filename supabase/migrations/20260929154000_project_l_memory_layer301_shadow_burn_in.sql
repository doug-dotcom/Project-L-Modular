-- Project L Memory Layer 301 — Shadow Burn-In Certification
--
-- Layer 300 introduced the master activation gate. Layer 301 prevents ACTIVE
-- from being reached merely because the stack is structurally healthy.
--
-- ACTIVE now additionally requires a current-generation shadow burn-in:
--   * >=72 hours in SHADOW_ONLY;
--   * >=20 eligible automatic observations;
--   * observations across >=3 distinct UTC days;
--   * >=8 distinct keyed exact-query fingerprints;
--   * >=5 distinct keyed lexical cohorts;
--   * >=5 proposals that would actually change retrieval mode;
--   * those mode-changing proposals span >=3 lexical cohorts.
--
-- Evidence is generation-bound. Leaving SHADOW_ONLY and later returning starts
-- a fresh burn-in; stale observations from an older shadow cycle cannot certify
-- a new activation.

alter table public.project_l_adaptive_memory_activation
  add column if not exists shadow_started_at timestamptz,
  add column if not exists activation_basis_shadow_generation bigint;

update public.project_l_adaptive_memory_activation
set shadow_started_at=coalesce(shadow_started_at,updated_at,created_at)
where id='global'
  and mode='shadow_only'
  and shadow_started_at is null;

create table if not exists public.project_l_adaptive_memory_shadow_observations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  request_id text not null,
  activation_generation bigint not null
    check (activation_generation >= 1),
  intent text not null,
  query_fingerprint text not null
    check (query_fingerprint ~ '^[0-9a-f]{64}$'),
  query_cohort_fingerprint text not null
    check (query_cohort_fingerprint ~ '^[0-9a-f]{64}$'),
  actual_mode text not null
    check (actual_mode in ('lexical','semantic','hybrid')),
  proposed_mode text not null
    check (proposed_mode in ('lexical','semantic','hybrid')),
  proposal_source text not null,
  proposal_reason text,
  proposal_would_change boolean not null,
  observed_at timestamptz not null,
  created_at timestamptz not null default now(),
  unique(user_id,request_id)
);

create index if not exists project_l_adaptive_memory_shadow_observations_generation_idx
  on public.project_l_adaptive_memory_shadow_observations(
    activation_generation,
    observed_at desc,
    id desc
  );

create index if not exists project_l_adaptive_memory_shadow_observations_cohort_idx
  on public.project_l_adaptive_memory_shadow_observations(
    activation_generation,
    query_cohort_fingerprint,
    observed_at desc
  );

alter table public.project_l_adaptive_memory_shadow_observations
  enable row level security;

revoke all on table public.project_l_adaptive_memory_shadow_observations
  from public, anon, authenticated;

grant select, insert on table public.project_l_adaptive_memory_shadow_observations
  to service_role;

create or replace function public.project_l_adaptive_shadow_certification_v1(
  p_generation bigint default null,
  p_now timestamptz default now()
)
returns jsonb
language plpgsql
stable
security invoker
set search_path = ''
set statement_timeout = '5s'
as $$
declare
  v_cfg public.project_l_adaptive_memory_activation%rowtype;
  v_generation bigint;
  v_shadow_started_at timestamptz;
  v_burn_in_hours numeric := 0;

  v_observation_count integer := 0;
  v_distinct_days integer := 0;
  v_distinct_exact_queries integer := 0;
  v_distinct_cohorts integer := 0;
  v_mode_change_count integer := 0;
  v_mode_change_cohorts integer := 0;
  v_distinct_intents integer := 0;
  v_first_observed_at timestamptz;
  v_last_observed_at timestamptz;

  v_certified boolean := false;
  v_missing jsonb;
begin
  select *
  into v_cfg
  from public.project_l_adaptive_memory_activation
  where id='global';

  if not found then
    return jsonb_build_object(
      'available',false,
      'certified',false,
      'reason','activation_config_missing'
    );
  end if;

  v_generation := coalesce(
    p_generation,
    case
      when v_cfg.mode='active'
        then v_cfg.activation_basis_shadow_generation
      else v_cfg.generation
    end
  );

  if v_generation is null or v_generation < 1 then
    return jsonb_build_object(
      'available',true,
      'certified',false,
      'generation',v_generation,
      'reason','shadow_generation_missing'
    );
  end if;

  -- The current shadow cycle start is authoritative while SHADOW_ONLY. Once
  -- ACTIVE, Layer 300 preserves it as the basis for the activation certificate.
  v_shadow_started_at := v_cfg.shadow_started_at;

  if v_shadow_started_at is not null then
    v_burn_in_hours :=
      round(
        greatest(
          0,
          extract(epoch from (p_now-v_shadow_started_at))/3600.0
        )::numeric,
        4
      );
  end if;

  select
    count(*),
    count(distinct ((observed_at at time zone 'UTC')::date)),
    count(distinct query_fingerprint),
    count(distinct query_cohort_fingerprint),
    count(*) filter (where proposal_would_change),
    count(distinct query_cohort_fingerprint)
      filter (where proposal_would_change),
    count(distinct intent),
    min(observed_at),
    max(observed_at)
  into
    v_observation_count,
    v_distinct_days,
    v_distinct_exact_queries,
    v_distinct_cohorts,
    v_mode_change_count,
    v_mode_change_cohorts,
    v_distinct_intents,
    v_first_observed_at,
    v_last_observed_at
  from public.project_l_adaptive_memory_shadow_observations
  where activation_generation=v_generation
    and (
      v_shadow_started_at is null
      or observed_at >= v_shadow_started_at
    )
    and observed_at <= p_now;

  v_certified :=
    v_shadow_started_at is not null
    and v_burn_in_hours >= 72
    and v_observation_count >= 20
    and v_distinct_days >= 3
    and v_distinct_exact_queries >= 8
    and v_distinct_cohorts >= 5
    and v_mode_change_count >= 5
    and v_mode_change_cohorts >= 3;

  select coalesce(
    jsonb_agg(name order by name),
    '[]'::jsonb
  )
  into v_missing
  from (
    values
      ('shadow_burn_in_72h',v_shadow_started_at is not null and v_burn_in_hours >= 72),
      ('shadow_observations_20',v_observation_count >= 20),
      ('shadow_distinct_days_3',v_distinct_days >= 3),
      ('shadow_exact_queries_8',v_distinct_exact_queries >= 8),
      ('shadow_lexical_cohorts_5',v_distinct_cohorts >= 5),
      ('shadow_mode_changes_5',v_mode_change_count >= 5),
      ('shadow_mode_change_cohorts_3',v_mode_change_cohorts >= 3)
  ) as requirements(name,ready)
  where not ready;

  return jsonb_build_object(
    'available',true,
    'version','layer301-v1',
    'certified',v_certified,
    'generation',v_generation,
    'shadowStartedAt',v_shadow_started_at,
    'burnInHours',v_burn_in_hours,
    'requirements',jsonb_build_object(
      'minimumBurnInHours',72,
      'minimumObservations',20,
      'minimumDistinctDays',3,
      'minimumDistinctExactQueries',8,
      'minimumDistinctLexicalCohorts',5,
      'minimumModeChangingProposals',5,
      'minimumModeChangingCohorts',3
    ),
    'observed',jsonb_build_object(
      'observationCount',v_observation_count,
      'distinctDays',v_distinct_days,
      'distinctExactQueries',v_distinct_exact_queries,
      'distinctLexicalCohorts',v_distinct_cohorts,
      'modeChangingProposals',v_mode_change_count,
      'modeChangingCohorts',v_mode_change_cohorts,
      'distinctIntents',v_distinct_intents,
      'firstObservedAt',v_first_observed_at,
      'lastObservedAt',v_last_observed_at
    ),
    'missing',v_missing,
    'reason',case
      when v_certified then 'shadow_burn_in_certified'
      else 'shadow_burn_in_incomplete'
    end
  );
end;
$$;

revoke all on function public.project_l_adaptive_shadow_certification_v1(
  bigint,timestamptz
) from public, anon, authenticated;

grant execute on function public.project_l_adaptive_shadow_certification_v1(
  bigint,timestamptz
) to service_role;

create or replace function public.project_l_record_adaptive_shadow_observation_v1(
  p_user uuid,
  p_request_id text,
  p_intent text,
  p_query_fingerprint text,
  p_query_cohort_fingerprint text,
  p_actual_mode text,
  p_proposed_mode text,
  p_proposal_source text,
  p_proposal_reason text default null,
  p_explicit_mode_used boolean default false,
  p_observed_at timestamptz default now()
)
returns jsonb
language plpgsql
volatile
security invoker
set search_path = ''
set statement_timeout = '5s'
as $$
declare
  v_request_id text := left(btrim(coalesce(p_request_id,'')),120);
  v_intent text := left(lower(btrim(coalesce(p_intent,''))),80);
  v_query_fingerprint text :=
    lower(btrim(coalesce(p_query_fingerprint,'')));
  v_cohort_fingerprint text :=
    lower(btrim(coalesce(p_query_cohort_fingerprint,'')));
  v_actual text := lower(btrim(coalesce(p_actual_mode,'')));
  v_proposed text := lower(btrim(coalesce(p_proposed_mode,'')));
  v_source text := left(btrim(coalesce(p_proposal_source,'')),80);
  v_reason text :=
    nullif(left(btrim(coalesce(p_proposal_reason,'')),240),'');
  v_status jsonb;
  v_generation bigint;
  v_id uuid;
  v_existing public.project_l_adaptive_memory_shadow_observations%rowtype;
begin
  if p_user is null then
    raise exception 'PROJECT_L_LAYER301_USER_REQUIRED';
  end if;
  if v_request_id='' then
    raise exception 'PROJECT_L_LAYER301_REQUEST_ID_REQUIRED';
  end if;
  if v_intent='' then
    raise exception 'PROJECT_L_LAYER301_INTENT_REQUIRED';
  end if;
  if v_query_fingerprint !~ '^[0-9a-f]{64}$' then
    raise exception 'PROJECT_L_LAYER301_INVALID_QUERY_FINGERPRINT';
  end if;
  if v_cohort_fingerprint !~ '^[0-9a-f]{64}$' then
    raise exception 'PROJECT_L_LAYER301_INVALID_COHORT_FINGERPRINT';
  end if;
  if v_actual not in ('lexical','semantic','hybrid')
     or v_proposed not in ('lexical','semantic','hybrid') then
    raise exception 'PROJECT_L_LAYER301_INVALID_MODE';
  end if;
  if v_source='' then
    raise exception 'PROJECT_L_LAYER301_PROPOSAL_SOURCE_REQUIRED';
  end if;

  if coalesce(p_explicit_mode_used,false) then
    return jsonb_build_object(
      'status','ignored',
      'recorded',false,
      'reason','explicit_request_not_shadow_burn_in'
    );
  end if;

  v_status := public.project_l_adaptive_memory_activation_status_v1();

  if coalesce(v_status->>'effectiveMode','shadow_only') <> 'shadow_only'
     or coalesce((v_status->>'shadowEvaluationEnabled')::boolean,false) is not true
     or coalesce((v_status->>'stackReady')::boolean,false) is not true
     or coalesce((v_status->>'runtimeInfluenceEnabled')::boolean,false) is true then
    return jsonb_build_object(
      'status','ignored',
      'recorded',false,
      'reason','not_eligible_shadow_state'
    );
  end if;

  v_generation := nullif(v_status->>'generation','')::bigint;

  if v_generation is null or v_generation < 1 then
    return jsonb_build_object(
      'status','ignored',
      'recorded',false,
      'reason','activation_generation_missing'
    );
  end if;

  insert into public.project_l_adaptive_memory_shadow_observations(
    user_id,
    request_id,
    activation_generation,
    intent,
    query_fingerprint,
    query_cohort_fingerprint,
    actual_mode,
    proposed_mode,
    proposal_source,
    proposal_reason,
    proposal_would_change,
    observed_at
  )
  values (
    p_user,
    v_request_id,
    v_generation,
    v_intent,
    v_query_fingerprint,
    v_cohort_fingerprint,
    v_actual,
    v_proposed,
    v_source,
    v_reason,
    v_actual<>v_proposed,
    p_observed_at
  )
  on conflict (user_id,request_id) do nothing
  returning id into v_id;

  if v_id is null then
    select *
    into v_existing
    from public.project_l_adaptive_memory_shadow_observations
    where user_id=p_user
      and request_id=v_request_id;

    if not found then
      raise exception 'PROJECT_L_LAYER301_DUPLICATE_LOOKUP_FAILED';
    end if;

    if v_existing.query_fingerprint<>v_query_fingerprint
       or v_existing.query_cohort_fingerprint<>v_cohort_fingerprint
       or v_existing.actual_mode<>v_actual
       or v_existing.proposed_mode<>v_proposed
       or v_existing.activation_generation<>v_generation then
      raise exception 'PROJECT_L_LAYER301_SHADOW_REPLAY_MISMATCH';
    end if;

    return jsonb_build_object(
      'status','already_recorded',
      'recorded',false,
      'observationId',v_existing.id,
      'generation',v_existing.activation_generation,
      'proposalWouldChange',v_existing.proposal_would_change
    );
  end if;

  return jsonb_build_object(
    'status','recorded',
    'recorded',true,
    'observationId',v_id,
    'generation',v_generation,
    'proposalWouldChange',v_actual<>v_proposed
  );
end;
$$;

revoke all on function public.project_l_record_adaptive_shadow_observation_v1(
  uuid,text,text,text,text,text,text,text,text,boolean,timestamptz
) from public, anon, authenticated;

grant execute on function public.project_l_record_adaptive_shadow_observation_v1(
  uuid,text,text,text,text,text,text,text,text,boolean,timestamptz
) to service_role;

-- Extend Layer 300 stack health to include the Layer 301 burn-in machinery.
create or replace function public.project_l_adaptive_memory_stack_health_v1()
returns jsonb
language plpgsql
stable
security invoker
set search_path = ''
set statement_timeout = '5s'
as $$
declare
  v_293 boolean :=
    to_regprocedure(
      'public.project_l_adaptive_strategy_drift_guard_v1(uuid,text,text,text,jsonb,timestamptz)'
    ) is not null;
  v_294 boolean :=
    to_regprocedure(
      'public.project_l_strategy_lease_status_v1(uuid,text,jsonb,timestamptz)'
    ) is not null;
  v_295 boolean :=
    to_regprocedure(
      'public.project_l_runtime_retrieval_decision_v1(uuid,text,text,text,boolean,boolean,timestamptz)'
    ) is not null;
  v_296_record boolean :=
    to_regprocedure(
      'public.project_l_record_served_outcome_v1(uuid,text,text,text,jsonb,timestamptz)'
    ) is not null;
  v_296_feed boolean :=
    to_regprocedure(
      'public.project_l_served_outcome_feed_v1(uuid,text,text,timestamptz,integer)'
    ) is not null;
  v_297 boolean :=
    to_regprocedure(
      'public.project_l_governed_lease_evaluation_v1(uuid,text,text,timestamptz)'
    ) is not null;
  v_298 boolean :=
    to_regprocedure(
      'public.project_l_record_served_outcome_bound_v1(uuid,text,text,text,text,jsonb,timestamptz)'
    ) is not null;
  v_299_record boolean :=
    to_regprocedure(
      'public.project_l_record_served_outcome_cohort_bound_v1(uuid,text,text,text,text,text,jsonb,timestamptz)'
    ) is not null;
  v_299_feed boolean :=
    to_regprocedure(
      'public.project_l_cohort_independent_served_outcome_feed_v1(uuid,text,timestamptz,integer)'
    ) is not null;
  v_301_record boolean :=
    to_regprocedure(
      'public.project_l_record_adaptive_shadow_observation_v1(uuid,text,text,text,text,text,text,text,text,boolean,timestamptz)'
    ) is not null;
  v_301_cert boolean :=
    to_regprocedure(
      'public.project_l_adaptive_shadow_certification_v1(bigint,timestamptz)'
    ) is not null;

  v_adaptation_table boolean :=
    to_regclass('public.project_l_retrieval_adaptation_events') is not null;
  v_lease_table boolean :=
    to_regclass('public.project_l_retrieval_strategy_leases') is not null;
  v_outcome_table boolean :=
    to_regclass('public.project_l_retrieval_served_outcomes') is not null;
  v_query_binding_table boolean :=
    to_regclass('public.project_l_retrieval_outcome_query_bindings') is not null;
  v_cohort_binding_table boolean :=
    to_regclass('public.project_l_retrieval_outcome_cohort_bindings') is not null;
  v_shadow_table boolean :=
    to_regclass('public.project_l_adaptive_memory_shadow_observations') is not null;

  v_adaptation_rls boolean := false;
  v_lease_rls boolean := false;
  v_outcome_rls boolean := false;
  v_query_binding_rls boolean := false;
  v_cohort_binding_rls boolean := false;
  v_shadow_rls boolean := false;

  v_stack_ready boolean;
  v_missing jsonb;
begin
  select coalesce(c.relrowsecurity,false)
  into v_adaptation_rls
  from pg_catalog.pg_class c
  join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public'
    and c.relname='project_l_retrieval_adaptation_events';

  select coalesce(c.relrowsecurity,false)
  into v_lease_rls
  from pg_catalog.pg_class c
  join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public'
    and c.relname='project_l_retrieval_strategy_leases';

  select coalesce(c.relrowsecurity,false)
  into v_outcome_rls
  from pg_catalog.pg_class c
  join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public'
    and c.relname='project_l_retrieval_served_outcomes';

  select coalesce(c.relrowsecurity,false)
  into v_query_binding_rls
  from pg_catalog.pg_class c
  join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public'
    and c.relname='project_l_retrieval_outcome_query_bindings';

  select coalesce(c.relrowsecurity,false)
  into v_cohort_binding_rls
  from pg_catalog.pg_class c
  join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public'
    and c.relname='project_l_retrieval_outcome_cohort_bindings';

  select coalesce(c.relrowsecurity,false)
  into v_shadow_rls
  from pg_catalog.pg_class c
  join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public'
    and c.relname='project_l_adaptive_memory_shadow_observations';

  v_stack_ready :=
    v_293 and v_294 and v_295
    and v_296_record and v_296_feed
    and v_297 and v_298
    and v_299_record and v_299_feed
    and v_301_record and v_301_cert
    and v_adaptation_table and coalesce(v_adaptation_rls,false)
    and v_lease_table and coalesce(v_lease_rls,false)
    and v_outcome_table and coalesce(v_outcome_rls,false)
    and v_query_binding_table and coalesce(v_query_binding_rls,false)
    and v_cohort_binding_table and coalesce(v_cohort_binding_rls,false)
    and v_shadow_table and coalesce(v_shadow_rls,false);

  select coalesce(jsonb_agg(name order by name),'[]'::jsonb)
  into v_missing
  from (
    values
      ('layer293_guard',v_293),
      ('layer294_lease_evaluator',v_294),
      ('layer295_runtime_selector',v_295),
      ('layer296_outcome_recorder',v_296_record),
      ('layer296_outcome_feed',v_296_feed),
      ('layer297_governed_evaluator',v_297),
      ('layer298_exact_binding',v_298),
      ('layer299_cohort_recorder',v_299_record),
      ('layer299_cohort_feed',v_299_feed),
      ('layer301_shadow_recorder',v_301_record),
      ('layer301_shadow_certificate',v_301_cert),
      ('adaptation_table_rls',v_adaptation_table and coalesce(v_adaptation_rls,false)),
      ('lease_table_rls',v_lease_table and coalesce(v_lease_rls,false)),
      ('outcome_table_rls',v_outcome_table and coalesce(v_outcome_rls,false)),
      ('query_binding_table_rls',v_query_binding_table and coalesce(v_query_binding_rls,false)),
      ('cohort_binding_table_rls',v_cohort_binding_table and coalesce(v_cohort_binding_rls,false)),
      ('shadow_observation_table_rls',v_shadow_table and coalesce(v_shadow_rls,false))
  ) as checks(name,ready)
  where not ready;

  return jsonb_build_object(
    'version','layer301-v1',
    'requiredLayerFloor',301,
    'stackReady',v_stack_ready,
    'missing',v_missing
  );
end;
$$;

-- Layer 300 status now additionally requires a valid burn-in certificate for
-- runtime influence. ACTIVE config without certification fails closed.
create or replace function public.project_l_adaptive_memory_activation_status_v1()
returns jsonb
language plpgsql
stable
security invoker
set search_path = ''
set statement_timeout = '5s'
as $$
declare
  v_cfg public.project_l_adaptive_memory_activation%rowtype;
  v_health jsonb;
  v_shadow_cert jsonb;
  v_stack_ready boolean := false;
  v_shadow_certified boolean := false;
  v_runtime_enabled boolean := false;
  v_effective_mode text := 'shadow_only';
begin
  select *
  into v_cfg
  from public.project_l_adaptive_memory_activation
  where id='global';

  if not found then
    return jsonb_build_object(
      'available',false,
      'configuredMode','shadow_only',
      'effectiveMode','shadow_only',
      'runtimeInfluenceEnabled',false,
      'shadowEvaluationEnabled',true,
      'stackReady',false,
      'shadowCertified',false,
      'generation',null,
      'reason','activation_config_missing'
    );
  end if;

  v_health := public.project_l_adaptive_memory_stack_health_v1();
  v_stack_ready := coalesce((v_health->>'stackReady')::boolean,false);

  v_shadow_cert := public.project_l_adaptive_shadow_certification_v1(
    case
      when v_cfg.mode='active'
        then v_cfg.activation_basis_shadow_generation
      else v_cfg.generation
    end,
    now()
  );
  v_shadow_certified :=
    coalesce((v_shadow_cert->>'certified')::boolean,false);

  v_runtime_enabled :=
    v_cfg.mode='active'
    and v_stack_ready
    and v_shadow_certified;

  v_effective_mode := case
    when v_runtime_enabled then 'active'
    when v_cfg.mode='disabled' then 'disabled'
    else 'shadow_only'
  end;

  return jsonb_build_object(
    'available',true,
    'configuredMode',v_cfg.mode,
    'effectiveMode',v_effective_mode,
    'runtimeInfluenceEnabled',v_runtime_enabled,
    'shadowEvaluationEnabled',v_cfg.mode in ('shadow_only','active'),
    'stackReady',v_stack_ready,
    'shadowCertified',v_shadow_certified,
    'shadowCertification',v_shadow_cert,
    'generation',v_cfg.generation,
    'activationBasisShadowGeneration',v_cfg.activation_basis_shadow_generation,
    'requiredLayerFloor',301,
    'reason',case
      when v_cfg.mode='active' and not v_stack_ready
        then 'configured_active_but_stack_unhealthy'
      when v_cfg.mode='active' and not v_shadow_certified
        then 'configured_active_but_shadow_uncertified'
      else v_cfg.reason
    end,
    'enabledAt',v_cfg.enabled_at,
    'shadowStartedAt',v_cfg.shadow_started_at,
    'updatedAt',v_cfg.updated_at,
    'stackHealth',v_health
  );
end;
$$;

-- Replace Layer 300 setter so ACTIVE additionally requires current shadow burn-in.
create or replace function public.project_l_set_adaptive_memory_activation_v1(
  p_mode text,
  p_reason text,
  p_expected_generation bigint,
  p_now timestamptz default now()
)
returns jsonb
language plpgsql
volatile
security invoker
set search_path = ''
set statement_timeout = '5s'
as $$
declare
  v_mode text := lower(btrim(coalesce(p_mode,'')));
  v_reason text := btrim(coalesce(p_reason,''));
  v_cfg public.project_l_adaptive_memory_activation%rowtype;
  v_health jsonb;
  v_shadow_cert jsonb;
  v_stack_ready boolean := false;
  v_shadow_certified boolean := false;
  v_new_generation bigint;
begin
  if v_mode not in ('disabled','shadow_only','active') then
    raise exception 'PROJECT_L_LAYER300_INVALID_MODE';
  end if;

  if length(v_reason) < 8 or length(v_reason) > 500 then
    raise exception 'PROJECT_L_LAYER300_REASON_LENGTH';
  end if;

  if p_expected_generation is null or p_expected_generation < 1 then
    raise exception 'PROJECT_L_LAYER300_EXPECTED_GENERATION_REQUIRED';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended('project_l_adaptive_memory_activation',301)
  );

  select *
  into v_cfg
  from public.project_l_adaptive_memory_activation
  where id='global'
  for update;

  if not found then
    raise exception 'PROJECT_L_LAYER300_CONFIG_MISSING';
  end if;

  if v_cfg.generation<>p_expected_generation then
    return jsonb_build_object(
      'status','conflict',
      'changed',false,
      'configuredMode',v_cfg.mode,
      'generation',v_cfg.generation,
      'reason','stale_expected_generation'
    );
  end if;

  v_health := public.project_l_adaptive_memory_stack_health_v1();
  v_stack_ready := coalesce((v_health->>'stackReady')::boolean,false);

  v_shadow_cert := public.project_l_adaptive_shadow_certification_v1(
    v_cfg.generation,
    p_now
  );
  v_shadow_certified :=
    coalesce((v_shadow_cert->>'certified')::boolean,false);

  if v_mode='active' and v_cfg.mode<>'shadow_only' then
    return jsonb_build_object(
      'status','blocked',
      'changed',false,
      'configuredMode',v_cfg.mode,
      'generation',v_cfg.generation,
      'reason','activation_requires_shadow_only_prestate',
      'stackHealth',v_health,
      'shadowCertification',v_shadow_cert
    );
  end if;

  if v_mode='active' and not v_stack_ready then
    return jsonb_build_object(
      'status','blocked',
      'changed',false,
      'configuredMode',v_cfg.mode,
      'generation',v_cfg.generation,
      'reason','activation_requires_healthy_stack',
      'stackHealth',v_health,
      'shadowCertification',v_shadow_cert
    );
  end if;

  if v_mode='active' and not v_shadow_certified then
    return jsonb_build_object(
      'status','blocked',
      'changed',false,
      'configuredMode',v_cfg.mode,
      'generation',v_cfg.generation,
      'reason','activation_requires_shadow_burn_in',
      'stackHealth',v_health,
      'shadowCertification',v_shadow_cert
    );
  end if;

  if v_mode=v_cfg.mode then
    return jsonb_build_object(
      'status','already_set',
      'changed',false,
      'configuredMode',v_cfg.mode,
      'generation',v_cfg.generation,
      'stackHealth',v_health,
      'shadowCertification',v_shadow_cert
    );
  end if;

  v_new_generation := v_cfg.generation+1;

  update public.project_l_adaptive_memory_activation
  set
    mode=v_mode,
    generation=v_new_generation,
    required_layer_floor=301,
    reason=v_reason,
    enabled_at=case when v_mode='active' then p_now else null end,
    shadow_started_at=case
      when v_mode='shadow_only' then p_now
      else shadow_started_at
    end,
    activation_basis_shadow_generation=case
      when v_mode='active' then v_cfg.generation
      else null
    end,
    updated_at=p_now
  where id='global';

  insert into public.project_l_adaptive_memory_activation_events(
    previous_mode,
    new_mode,
    previous_generation,
    new_generation,
    reason,
    stack_snapshot,
    changed_at
  )
  values (
    v_cfg.mode,
    v_mode,
    v_cfg.generation,
    v_new_generation,
    v_reason,
    jsonb_build_object(
      'stackHealth',v_health,
      'shadowCertification',v_shadow_cert
    ),
    p_now
  );

  return jsonb_build_object(
    'status','changed',
    'changed',true,
    'previousMode',v_cfg.mode,
    'configuredMode',v_mode,
    'previousGeneration',v_cfg.generation,
    'generation',v_new_generation,
    'runtimeInfluenceEnabled',
      v_mode='active' and v_stack_ready and v_shadow_certified,
    'activationBasisShadowGeneration',
      case when v_mode='active' then v_cfg.generation else null end,
    'stackHealth',v_health,
    'shadowCertification',v_shadow_cert
  );
end;
$$;

comment on table public.project_l_adaptive_memory_shadow_observations is
  'Layer 301 append-only, content-free shadow burn-in observations bound to one activation generation.';

comment on function public.project_l_adaptive_shadow_certification_v1(
  bigint,timestamptz
) is
  'Layer 301 read-only burn-in certificate requiring time, volume, temporal spread, keyed query/cohort breadth, and meaningful mode-changing proposals.';

comment on function public.project_l_record_adaptive_shadow_observation_v1(
  uuid,text,text,text,text,text,text,text,text,boolean,timestamptz
) is
  'Layer 301 idempotent shadow observation recorder; explicit requests and non-shadow/unhealthy states do not count toward burn-in.';

comment on function public.project_l_adaptive_memory_activation_status_v1() is
  'Layers 300-301 effective activation status: ACTIVE runtime influence requires stack health plus a current-generation shadow burn-in certificate.';

comment on function public.project_l_set_adaptive_memory_activation_v1(
  text,text,bigint,timestamptz
) is
  'Layers 300-301 compare-and-swap activation control requiring healthy stack and certified current-generation shadow burn-in before ACTIVE.';
