-- Project L Memory Layer 303 — Shadow Counterfactual Sampling Budget
--
-- Layer 302 can execute an unused alternate retrieval path to prove quality.
-- Layer 303 bounds that extra work so shadow certification cannot become an
-- unbounded double-retrieval tax.
--
-- Admission budget:
--   * maximum 4 admitted counterfactuals per user per UTC day;
--   * maximum 1 admitted counterfactual per lexical cohort per UTC day;
--   * maximum 28 admitted counterfactuals per activation generation;
--   * once Layer 302 quality is certified, no further samples are admitted.
--
-- Admission is a durable reservation. An admitted request consumes its slot
-- even if the alternate retrieval later fails, preventing retry amplification.

create table if not exists public.project_l_adaptive_memory_counterfactual_sampling (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  request_id text not null,
  activation_generation bigint not null check (activation_generation >= 1),
  intent text not null,
  query_fingerprint text not null check (query_fingerprint ~ '^[0-9a-f]{64}$'),
  query_cohort_fingerprint text not null check (query_cohort_fingerprint ~ '^[0-9a-f]{64}$'),
  actual_mode text not null check (actual_mode in ('lexical','semantic','hybrid')),
  proposed_mode text not null check (proposed_mode in ('lexical','semantic','hybrid')),
  admitted boolean not null,
  decision_reason text not null,
  utc_day date not null,
  daily_admitted_before integer not null check (daily_admitted_before >= 0),
  cohort_daily_admitted_before integer not null check (cohort_daily_admitted_before >= 0),
  generation_admitted_before integer not null check (generation_admitted_before >= 0),
  quality_certified_before boolean not null default false,
  observed_at timestamptz not null,
  created_at timestamptz not null default now(),
  unique(user_id,request_id)
);

create index if not exists project_l_counterfactual_sampling_daily_idx
  on public.project_l_adaptive_memory_counterfactual_sampling(
    user_id,activation_generation,utc_day,admitted
  );

create index if not exists project_l_counterfactual_sampling_cohort_idx
  on public.project_l_adaptive_memory_counterfactual_sampling(
    user_id,activation_generation,utc_day,query_cohort_fingerprint,admitted
  );

alter table public.project_l_adaptive_memory_counterfactual_sampling
  enable row level security;

revoke all on table public.project_l_adaptive_memory_counterfactual_sampling
  from public, anon, authenticated;

grant select, insert on table public.project_l_adaptive_memory_counterfactual_sampling
  to service_role;

create or replace function public.project_l_adaptive_counterfactual_sampling_status_v1(
  p_user uuid,
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
  v_day date := (p_now at time zone 'UTC')::date;
  v_daily integer := 0;
  v_generation_total integer := 0;
  v_quality jsonb;
  v_quality_certified boolean := false;
begin
  if p_user is null then
    raise exception 'PROJECT_L_LAYER303_USER_REQUIRED';
  end if;

  select *
  into v_cfg
  from public.project_l_adaptive_memory_activation
  where id='global';

  if not found then
    return jsonb_build_object(
      'available',false,
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

  if v_generation is null or v_generation<1 then
    return jsonb_build_object(
      'available',true,
      'generation',v_generation,
      'samplingOpen',false,
      'reason','shadow_generation_missing'
    );
  end if;

  select count(*)
  into v_daily
  from public.project_l_adaptive_memory_counterfactual_sampling
  where user_id=p_user
    and activation_generation=v_generation
    and utc_day=v_day
    and admitted=true;

  select count(*)
  into v_generation_total
  from public.project_l_adaptive_memory_counterfactual_sampling
  where user_id=p_user
    and activation_generation=v_generation
    and admitted=true;

  v_quality := public.project_l_adaptive_counterfactual_certification_v1(
    v_generation,p_now
  );
  v_quality_certified :=
    coalesce((v_quality->>'certified')::boolean,false);

  return jsonb_build_object(
    'available',true,
    'version','layer303-v1',
    'generation',v_generation,
    'utcDay',v_day,
    'dailyAdmitted',v_daily,
    'dailyLimit',4,
    'generationAdmitted',v_generation_total,
    'generationLimit',28,
    'dailyRemaining',greatest(0,4-v_daily),
    'generationRemaining',greatest(0,28-v_generation_total),
    'qualityCertified',v_quality_certified,
    'samplingOpen',
      not v_quality_certified
      and v_daily<4
      and v_generation_total<28,
    'reason',case
      when v_quality_certified then 'quality_already_certified'
      when v_generation_total>=28 then 'generation_budget_exhausted'
      when v_daily>=4 then 'daily_budget_exhausted'
      else 'sampling_budget_available'
    end
  );
end;
$$;

revoke all on function public.project_l_adaptive_counterfactual_sampling_status_v1(
  uuid,bigint,timestamptz
) from public, anon, authenticated;

grant execute on function public.project_l_adaptive_counterfactual_sampling_status_v1(
  uuid,bigint,timestamptz
) to service_role;

create or replace function public.project_l_adaptive_counterfactual_sample_admission_v1(
  p_user uuid,
  p_request_id text,
  p_intent text,
  p_query_fingerprint text,
  p_query_cohort_fingerprint text,
  p_actual_mode text,
  p_proposed_mode text,
  p_explicit_mode_used boolean default false,
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
  v_request_id text := left(btrim(coalesce(p_request_id,'')),120);
  v_intent text := left(lower(btrim(coalesce(p_intent,''))),80);
  v_query_fingerprint text := lower(btrim(coalesce(p_query_fingerprint,'')));
  v_cohort_fingerprint text := lower(btrim(coalesce(p_query_cohort_fingerprint,'')));
  v_actual text := lower(btrim(coalesce(p_actual_mode,'')));
  v_proposed text := lower(btrim(coalesce(p_proposed_mode,'')));

  v_activation jsonb;
  v_generation bigint;
  v_day date := (p_now at time zone 'UTC')::date;
  v_quality jsonb;
  v_quality_certified boolean := false;

  v_daily integer := 0;
  v_cohort_daily integer := 0;
  v_generation_total integer := 0;

  v_admitted boolean := false;
  v_reason text;
  v_id uuid;
  v_existing public.project_l_adaptive_memory_counterfactual_sampling%rowtype;
begin
  if p_user is null then
    raise exception 'PROJECT_L_LAYER303_USER_REQUIRED';
  end if;
  if v_request_id='' then
    raise exception 'PROJECT_L_LAYER303_REQUEST_ID_REQUIRED';
  end if;
  if v_intent='' then
    raise exception 'PROJECT_L_LAYER303_INTENT_REQUIRED';
  end if;
  if v_query_fingerprint !~ '^[0-9a-f]{64}$' then
    raise exception 'PROJECT_L_LAYER303_INVALID_QUERY_FINGERPRINT';
  end if;
  if v_cohort_fingerprint !~ '^[0-9a-f]{64}$' then
    raise exception 'PROJECT_L_LAYER303_INVALID_COHORT_FINGERPRINT';
  end if;
  if v_actual not in ('lexical','semantic','hybrid')
     or v_proposed not in ('lexical','semantic','hybrid') then
    raise exception 'PROJECT_L_LAYER303_INVALID_MODE';
  end if;

  if coalesce(p_explicit_mode_used,false) then
    return jsonb_build_object(
      'status','ignored',
      'admitted',false,
      'reason','explicit_request_not_sampling_candidate'
    );
  end if;

  if v_actual=v_proposed then
    return jsonb_build_object(
      'status','ignored',
      'admitted',false,
      'reason','sampling_requires_mode_change'
    );
  end if;

  v_activation := public.project_l_adaptive_memory_activation_status_v1();

  if coalesce(v_activation->>'effectiveMode','shadow_only')<>'shadow_only'
     or coalesce((v_activation->>'shadowEvaluationEnabled')::boolean,false) is not true
     or coalesce((v_activation->>'stackReady')::boolean,false) is not true
     or coalesce((v_activation->>'runtimeInfluenceEnabled')::boolean,false) is true then
    return jsonb_build_object(
      'status','ignored',
      'admitted',false,
      'reason','not_eligible_shadow_state'
    );
  end if;

  v_generation := nullif(v_activation->>'generation','')::bigint;

  if v_generation is null or v_generation<1 then
    return jsonb_build_object(
      'status','ignored',
      'admitted',false,
      'reason','activation_generation_missing'
    );
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(
      p_user::text||'|'||v_generation::text||'|'||v_day::text,
      303
    )
  );

  select *
  into v_existing
  from public.project_l_adaptive_memory_counterfactual_sampling
  where user_id=p_user
    and request_id=v_request_id;

  if found then
    if v_existing.activation_generation<>v_generation
       or v_existing.query_fingerprint<>v_query_fingerprint
       or v_existing.query_cohort_fingerprint<>v_cohort_fingerprint
       or v_existing.actual_mode<>v_actual
       or v_existing.proposed_mode<>v_proposed then
      raise exception 'PROJECT_L_LAYER303_SAMPLING_REPLAY_MISMATCH';
    end if;

    return jsonb_build_object(
      'status','already_decided',
      'admitted',v_existing.admitted,
      'reason',v_existing.decision_reason,
      'generation',v_existing.activation_generation,
      'dailyAdmittedBefore',v_existing.daily_admitted_before,
      'cohortDailyAdmittedBefore',v_existing.cohort_daily_admitted_before,
      'generationAdmittedBefore',v_existing.generation_admitted_before,
      'qualityCertifiedBefore',v_existing.quality_certified_before
    );
  end if;

  v_quality := public.project_l_adaptive_counterfactual_certification_v1(
    v_generation,p_now
  );
  v_quality_certified :=
    coalesce((v_quality->>'certified')::boolean,false);

  select count(*)
  into v_daily
  from public.project_l_adaptive_memory_counterfactual_sampling
  where user_id=p_user
    and activation_generation=v_generation
    and utc_day=v_day
    and admitted=true;

  select count(*)
  into v_cohort_daily
  from public.project_l_adaptive_memory_counterfactual_sampling
  where user_id=p_user
    and activation_generation=v_generation
    and utc_day=v_day
    and query_cohort_fingerprint=v_cohort_fingerprint
    and admitted=true;

  select count(*)
  into v_generation_total
  from public.project_l_adaptive_memory_counterfactual_sampling
  where user_id=p_user
    and activation_generation=v_generation
    and admitted=true;

  if v_quality_certified then
    v_reason := 'quality_already_certified';
  elsif v_generation_total>=28 then
    v_reason := 'generation_budget_exhausted';
  elsif v_daily>=4 then
    v_reason := 'daily_budget_exhausted';
  elsif v_cohort_daily>=1 then
    v_reason := 'cohort_daily_budget_exhausted';
  else
    v_admitted := true;
    v_reason := 'counterfactual_sample_admitted';
  end if;

  insert into public.project_l_adaptive_memory_counterfactual_sampling(
    user_id,
    request_id,
    activation_generation,
    intent,
    query_fingerprint,
    query_cohort_fingerprint,
    actual_mode,
    proposed_mode,
    admitted,
    decision_reason,
    utc_day,
    daily_admitted_before,
    cohort_daily_admitted_before,
    generation_admitted_before,
    quality_certified_before,
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
    v_admitted,
    v_reason,
    v_day,
    v_daily,
    v_cohort_daily,
    v_generation_total,
    v_quality_certified,
    p_now
  )
  returning id into v_id;

  return jsonb_build_object(
    'status','decided',
    'decisionId',v_id,
    'admitted',v_admitted,
    'reason',v_reason,
    'generation',v_generation,
    'utcDay',v_day,
    'dailyAdmittedBefore',v_daily,
    'dailyLimit',4,
    'cohortDailyAdmittedBefore',v_cohort_daily,
    'cohortDailyLimit',1,
    'generationAdmittedBefore',v_generation_total,
    'generationLimit',28,
    'qualityCertifiedBefore',v_quality_certified,
    'reservationConsumesBudget',v_admitted
  );
end;
$$;

revoke all on function public.project_l_adaptive_counterfactual_sample_admission_v1(
  uuid,text,text,text,text,text,text,boolean,timestamptz
) from public, anon, authenticated;

grant execute on function public.project_l_adaptive_counterfactual_sample_admission_v1(
  uuid,text,text,text,text,text,text,boolean,timestamptz
) to service_role;

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
    to_regprocedure('public.project_l_adaptive_strategy_drift_guard_v1(uuid,text,text,text,jsonb,timestamptz)') is not null;
  v_294 boolean :=
    to_regprocedure('public.project_l_strategy_lease_status_v1(uuid,text,jsonb,timestamptz)') is not null;
  v_295 boolean :=
    to_regprocedure('public.project_l_runtime_retrieval_decision_v1(uuid,text,text,text,boolean,boolean,timestamptz)') is not null;
  v_296_record boolean :=
    to_regprocedure('public.project_l_record_served_outcome_v1(uuid,text,text,text,jsonb,timestamptz)') is not null;
  v_296_feed boolean :=
    to_regprocedure('public.project_l_served_outcome_feed_v1(uuid,text,text,timestamptz,integer)') is not null;
  v_297 boolean :=
    to_regprocedure('public.project_l_governed_lease_evaluation_v1(uuid,text,text,timestamptz)') is not null;
  v_298 boolean :=
    to_regprocedure('public.project_l_record_served_outcome_bound_v1(uuid,text,text,text,text,jsonb,timestamptz)') is not null;
  v_299_record boolean :=
    to_regprocedure('public.project_l_record_served_outcome_cohort_bound_v1(uuid,text,text,text,text,text,jsonb,timestamptz)') is not null;
  v_299_feed boolean :=
    to_regprocedure('public.project_l_cohort_independent_served_outcome_feed_v1(uuid,text,timestamptz,integer)') is not null;
  v_301_record boolean :=
    to_regprocedure('public.project_l_record_adaptive_shadow_observation_v1(uuid,text,text,text,text,text,text,text,text,boolean,timestamptz)') is not null;
  v_301_cert boolean :=
    to_regprocedure('public.project_l_adaptive_shadow_certification_v1(bigint,timestamptz)') is not null;
  v_302_score boolean :=
    to_regprocedure('public.project_l_retrieval_proxy_score_v1(jsonb)') is not null;
  v_302_record boolean :=
    to_regprocedure('public.project_l_record_adaptive_shadow_counterfactual_v1(uuid,text,text,text,text,text,text,text,text,jsonb,jsonb,boolean,timestamptz)') is not null;
  v_302_cert boolean :=
    to_regprocedure('public.project_l_adaptive_counterfactual_certification_v1(bigint,timestamptz)') is not null;
  v_303_admission boolean :=
    to_regprocedure('public.project_l_adaptive_counterfactual_sample_admission_v1(uuid,text,text,text,text,text,text,boolean,timestamptz)') is not null;
  v_303_status boolean :=
    to_regprocedure('public.project_l_adaptive_counterfactual_sampling_status_v1(uuid,bigint,timestamptz)') is not null;

  v_adaptation_table boolean := to_regclass('public.project_l_retrieval_adaptation_events') is not null;
  v_lease_table boolean := to_regclass('public.project_l_retrieval_strategy_leases') is not null;
  v_outcome_table boolean := to_regclass('public.project_l_retrieval_served_outcomes') is not null;
  v_query_binding_table boolean := to_regclass('public.project_l_retrieval_outcome_query_bindings') is not null;
  v_cohort_binding_table boolean := to_regclass('public.project_l_retrieval_outcome_cohort_bindings') is not null;
  v_shadow_table boolean := to_regclass('public.project_l_adaptive_memory_shadow_observations') is not null;
  v_counterfactual_table boolean := to_regclass('public.project_l_adaptive_memory_shadow_counterfactuals') is not null;
  v_sampling_table boolean := to_regclass('public.project_l_adaptive_memory_counterfactual_sampling') is not null;

  v_adaptation_rls boolean := false;
  v_lease_rls boolean := false;
  v_outcome_rls boolean := false;
  v_query_binding_rls boolean := false;
  v_cohort_binding_rls boolean := false;
  v_shadow_rls boolean := false;
  v_counterfactual_rls boolean := false;
  v_sampling_rls boolean := false;

  v_stack_ready boolean;
  v_missing jsonb;
begin
  select coalesce(c.relrowsecurity,false)
  into v_adaptation_rls
  from pg_catalog.pg_class c join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relname='project_l_retrieval_adaptation_events';

  select coalesce(c.relrowsecurity,false)
  into v_lease_rls
  from pg_catalog.pg_class c join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relname='project_l_retrieval_strategy_leases';

  select coalesce(c.relrowsecurity,false)
  into v_outcome_rls
  from pg_catalog.pg_class c join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relname='project_l_retrieval_served_outcomes';

  select coalesce(c.relrowsecurity,false)
  into v_query_binding_rls
  from pg_catalog.pg_class c join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relname='project_l_retrieval_outcome_query_bindings';

  select coalesce(c.relrowsecurity,false)
  into v_cohort_binding_rls
  from pg_catalog.pg_class c join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relname='project_l_retrieval_outcome_cohort_bindings';

  select coalesce(c.relrowsecurity,false)
  into v_shadow_rls
  from pg_catalog.pg_class c join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relname='project_l_adaptive_memory_shadow_observations';

  select coalesce(c.relrowsecurity,false)
  into v_counterfactual_rls
  from pg_catalog.pg_class c join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relname='project_l_adaptive_memory_shadow_counterfactuals';

  select coalesce(c.relrowsecurity,false)
  into v_sampling_rls
  from pg_catalog.pg_class c join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relname='project_l_adaptive_memory_counterfactual_sampling';

  v_stack_ready :=
    v_293 and v_294 and v_295
    and v_296_record and v_296_feed
    and v_297 and v_298
    and v_299_record and v_299_feed
    and v_301_record and v_301_cert
    and v_302_score and v_302_record and v_302_cert
    and v_303_admission and v_303_status
    and v_adaptation_table and coalesce(v_adaptation_rls,false)
    and v_lease_table and coalesce(v_lease_rls,false)
    and v_outcome_table and coalesce(v_outcome_rls,false)
    and v_query_binding_table and coalesce(v_query_binding_rls,false)
    and v_cohort_binding_table and coalesce(v_cohort_binding_rls,false)
    and v_shadow_table and coalesce(v_shadow_rls,false)
    and v_counterfactual_table and coalesce(v_counterfactual_rls,false)
    and v_sampling_table and coalesce(v_sampling_rls,false);

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
      ('layer302_proxy_score',v_302_score),
      ('layer302_counterfactual_recorder',v_302_record),
      ('layer302_counterfactual_certificate',v_302_cert),
      ('layer303_sample_admission',v_303_admission),
      ('layer303_sampling_status',v_303_status),
      ('adaptation_table_rls',v_adaptation_table and coalesce(v_adaptation_rls,false)),
      ('lease_table_rls',v_lease_table and coalesce(v_lease_rls,false)),
      ('outcome_table_rls',v_outcome_table and coalesce(v_outcome_rls,false)),
      ('query_binding_table_rls',v_query_binding_table and coalesce(v_query_binding_rls,false)),
      ('cohort_binding_table_rls',v_cohort_binding_table and coalesce(v_cohort_binding_rls,false)),
      ('shadow_observation_table_rls',v_shadow_table and coalesce(v_shadow_rls,false)),
      ('shadow_counterfactual_table_rls',v_counterfactual_table and coalesce(v_counterfactual_rls,false)),
      ('counterfactual_sampling_table_rls',v_sampling_table and coalesce(v_sampling_rls,false))
  ) as checks(name,ready)
  where not ready;

  return jsonb_build_object(
    'version','layer303-v1',
    'requiredLayerFloor',303,
    'stackReady',v_stack_ready,
    'missing',v_missing
  );
end;
$$;

-- ACTIVE runtime influence now requires both Layer 301 burn-in and Layer 302
-- counterfactual quality certification.
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
  v_counter_cert jsonb;
  v_stack_ready boolean := false;
  v_shadow_certified boolean := false;
  v_counter_certified boolean := false;
  v_runtime_enabled boolean := false;
  v_effective_mode text := 'shadow_only';
  v_basis_generation bigint;
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
      'counterfactualCertified',false,
      'generation',null,
      'reason','activation_config_missing'
    );
  end if;

  v_health := public.project_l_adaptive_memory_stack_health_v1();
  v_stack_ready := coalesce((v_health->>'stackReady')::boolean,false);

  v_basis_generation := case
    when v_cfg.mode='active'
      then v_cfg.activation_basis_shadow_generation
    else v_cfg.generation
  end;

  v_shadow_cert := public.project_l_adaptive_shadow_certification_v1(
    v_basis_generation,
    now()
  );
  v_shadow_certified :=
    coalesce((v_shadow_cert->>'certified')::boolean,false);

  v_counter_cert := public.project_l_adaptive_counterfactual_certification_v1(
    v_basis_generation,
    now()
  );
  v_counter_certified :=
    coalesce((v_counter_cert->>'certified')::boolean,false);

  v_runtime_enabled :=
    v_cfg.mode='active'
    and v_stack_ready
    and v_shadow_certified
    and v_counter_certified;

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
    'counterfactualCertified',v_counter_certified,
    'shadowCertification',v_shadow_cert,
    'counterfactualCertification',v_counter_cert,
    'generation',v_cfg.generation,
    'activationBasisShadowGeneration',v_cfg.activation_basis_shadow_generation,
    'requiredLayerFloor',303,
    'reason',case
      when v_cfg.mode='active' and not v_stack_ready
        then 'configured_active_but_stack_unhealthy'
      when v_cfg.mode='active' and not v_shadow_certified
        then 'configured_active_but_shadow_uncertified'
      when v_cfg.mode='active' and not v_counter_certified
        then 'configured_active_but_counterfactual_uncertified'
      else v_cfg.reason
    end,
    'enabledAt',v_cfg.enabled_at,
    'shadowStartedAt',v_cfg.shadow_started_at,
    'updatedAt',v_cfg.updated_at,
    'stackHealth',v_health
  );
end;
$$;

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
  v_counter_cert jsonb;
  v_stack_ready boolean := false;
  v_shadow_certified boolean := false;
  v_counter_certified boolean := false;
  v_new_generation bigint;
begin
  if v_mode not in ('disabled','shadow_only','active') then
    raise exception 'PROJECT_L_LAYER300_INVALID_MODE';
  end if;
  if length(v_reason)<8 or length(v_reason)>500 then
    raise exception 'PROJECT_L_LAYER300_REASON_LENGTH';
  end if;
  if p_expected_generation is null or p_expected_generation<1 then
    raise exception 'PROJECT_L_LAYER300_EXPECTED_GENERATION_REQUIRED';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended('project_l_adaptive_memory_activation',303)
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

  v_counter_cert := public.project_l_adaptive_counterfactual_certification_v1(
    v_cfg.generation,
    p_now
  );
  v_counter_certified :=
    coalesce((v_counter_cert->>'certified')::boolean,false);

  if v_mode='active' and v_cfg.mode<>'shadow_only' then
    return jsonb_build_object(
      'status','blocked',
      'changed',false,
      'configuredMode',v_cfg.mode,
      'generation',v_cfg.generation,
      'reason','activation_requires_shadow_only_prestate',
      'stackHealth',v_health,
      'shadowCertification',v_shadow_cert,
      'counterfactualCertification',v_counter_cert
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
      'shadowCertification',v_shadow_cert,
      'counterfactualCertification',v_counter_cert
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
      'shadowCertification',v_shadow_cert,
      'counterfactualCertification',v_counter_cert
    );
  end if;

  if v_mode='active' and not v_counter_certified then
    return jsonb_build_object(
      'status','blocked',
      'changed',false,
      'configuredMode',v_cfg.mode,
      'generation',v_cfg.generation,
      'reason','activation_requires_counterfactual_shadow_quality',
      'stackHealth',v_health,
      'shadowCertification',v_shadow_cert,
      'counterfactualCertification',v_counter_cert
    );
  end if;

  if v_mode=v_cfg.mode then
    return jsonb_build_object(
      'status','already_set',
      'changed',false,
      'configuredMode',v_cfg.mode,
      'generation',v_cfg.generation,
      'stackHealth',v_health,
      'shadowCertification',v_shadow_cert,
      'counterfactualCertification',v_counter_cert
    );
  end if;

  v_new_generation := v_cfg.generation+1;

  update public.project_l_adaptive_memory_activation
  set
    mode=v_mode,
    generation=v_new_generation,
    required_layer_floor=303,
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
      'shadowCertification',v_shadow_cert,
      'counterfactualCertification',v_counter_cert
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
      v_mode='active'
      and v_stack_ready
      and v_shadow_certified
      and v_counter_certified,
    'activationBasisShadowGeneration',
      case when v_mode='active' then v_cfg.generation else null end,
    'stackHealth',v_health,
    'shadowCertification',v_shadow_cert,
    'counterfactualCertification',v_counter_cert
  );
end;
$$;


comment on table public.project_l_adaptive_memory_counterfactual_sampling is
  'Layer 303 append-only durable admission ledger for bounded shadow counterfactual execution. An admission is a budget reservation even if later retrieval fails.';

comment on function public.project_l_adaptive_counterfactual_sampling_status_v1(
  uuid,bigint,timestamptz
) is
  'Layer 303 read-only sampling budget status: max 4/day, max 28/generation, and stop after Layer 302 certification.';

comment on function public.project_l_adaptive_counterfactual_sample_admission_v1(
  uuid,text,text,text,text,text,text,boolean,timestamptz
) is
  'Layer 303 deterministic admission gate: one cohort sample per day, four total per day, 28 per generation, durable reservation, no retries around the budget.';

comment on function public.project_l_adaptive_memory_stack_health_v1() is
  'Layers 300-303 stack health: adaptive activation requires the bounded counterfactual sampling controls as well as prior retrieval/evidence safeguards.';

comment on function public.project_l_adaptive_memory_activation_status_v1() is
  'Layers 300-303 activation status: ACTIVE requires the full adaptive stack including Layer 303 bounded shadow sampling controls.';

comment on function public.project_l_set_adaptive_memory_activation_v1(
  text,text,bigint,timestamptz
) is
  'Layers 300-303 activation control: required layer floor 303 with stack health, burn-in, counterfactual quality and bounded sampling safeguards.';
