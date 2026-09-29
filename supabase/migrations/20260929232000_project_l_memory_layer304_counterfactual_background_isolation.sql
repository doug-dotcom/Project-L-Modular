-- Project L Memory Layer 304 — Counterfactual Background Isolation & Reliability
--
-- Layer 303 bounds how often counterfactual shadow retrieval may run. Layer 304
-- removes that experimental work from the user response path and certifies that
-- the alternate execution itself is reliable.
--
-- Runtime design:
--   * admitted counterfactual work runs through EdgeRuntime.waitUntil();
--   * the HTTP response does not await alternate retrieval;
--   * a 1200ms evidence deadline prevents slow work from producing quality data;
--   * Layer 303's durable admission reservation still consumes budget even when
--     the alternate task times out or fails.
--
-- ACTIVE now additionally requires counterfactual execution reliability:
--   * >=10 admitted reservations;
--   * >=85% of admitted work reaches a terminal execution receipt;
--   * >=75% completes successfully;
--   * <=15% timeout share;
--   * <=15% failure share;
--   * no accepted completed comparison may report >1500ms duration.
--
-- The 1200ms deadline is an evidence deadline. Supabase's built-in embedding
-- session does not expose a cancellation signal, so Layer 303 remains the
-- compute-amplification boundary.

create table if not exists public.project_l_adaptive_memory_counterfactual_executions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  request_id text not null,
  activation_generation bigint not null check (activation_generation >= 1),
  terminal_status text not null
    check (terminal_status in ('completed','timed_out','failed')),
  duration_ms numeric not null check (duration_ms >= 0 and duration_ms <= 10000),
  error_code text,
  observed_at timestamptz not null,
  created_at timestamptz not null default now(),
  unique(user_id,request_id),
  foreign key(user_id,request_id)
    references public.project_l_adaptive_memory_counterfactual_sampling(user_id,request_id)
    on delete restrict
);

create index if not exists project_l_counterfactual_execution_generation_idx
  on public.project_l_adaptive_memory_counterfactual_executions(
    activation_generation,
    terminal_status,
    observed_at desc
  );

alter table public.project_l_adaptive_memory_counterfactual_executions
  enable row level security;

revoke all on table public.project_l_adaptive_memory_counterfactual_executions
  from public, anon, authenticated;

grant select, insert on table public.project_l_adaptive_memory_counterfactual_executions
  to service_role;

create or replace function public.project_l_record_adaptive_counterfactual_execution_v1(
  p_user uuid,
  p_request_id text,
  p_status text,
  p_duration_ms numeric,
  p_error_code text default null,
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
  v_status text := lower(btrim(coalesce(p_status,'')));
  v_error_code text := nullif(left(btrim(coalesce(p_error_code,'')),120),'');
  v_duration numeric := round(greatest(0,coalesce(p_duration_ms,0))::numeric,3);
  v_sampling public.project_l_adaptive_memory_counterfactual_sampling%rowtype;
  v_quality_exists boolean := false;
  v_id uuid;
  v_existing public.project_l_adaptive_memory_counterfactual_executions%rowtype;
begin
  if p_user is null then
    raise exception 'PROJECT_L_LAYER304_USER_REQUIRED';
  end if;
  if v_request_id='' then
    raise exception 'PROJECT_L_LAYER304_REQUEST_ID_REQUIRED';
  end if;
  if v_status not in ('completed','timed_out','failed') then
    raise exception 'PROJECT_L_LAYER304_INVALID_STATUS';
  end if;
  if v_duration>10000 then
    raise exception 'PROJECT_L_LAYER304_DURATION_OUT_OF_RANGE';
  end if;

  select *
  into v_sampling
  from public.project_l_adaptive_memory_counterfactual_sampling
  where user_id=p_user
    and request_id=v_request_id;

  if not found then
    raise exception 'PROJECT_L_LAYER304_SAMPLING_RESERVATION_REQUIRED';
  end if;

  if not v_sampling.admitted then
    raise exception 'PROJECT_L_LAYER304_ADMITTED_RESERVATION_REQUIRED';
  end if;

  if v_status='completed' and v_duration>1500 then
    raise exception 'PROJECT_L_LAYER304_COMPLETED_OVER_BUDGET';
  end if;

  if v_status='completed' then
    select exists(
      select 1
      from public.project_l_adaptive_memory_shadow_counterfactuals
      where user_id=p_user
        and request_id=v_request_id
        and activation_generation=v_sampling.activation_generation
    )
    into v_quality_exists;

    if not v_quality_exists then
      raise exception 'PROJECT_L_LAYER304_COMPLETED_QUALITY_RECEIPT_REQUIRED';
    end if;
  end if;

  insert into public.project_l_adaptive_memory_counterfactual_executions(
    user_id,
    request_id,
    activation_generation,
    terminal_status,
    duration_ms,
    error_code,
    observed_at
  )
  values (
    p_user,
    v_request_id,
    v_sampling.activation_generation,
    v_status,
    v_duration,
    case when v_status='completed' then null else coalesce(v_error_code,'unspecified') end,
    p_observed_at
  )
  on conflict (user_id,request_id) do nothing
  returning id into v_id;

  if v_id is null then
    select *
    into v_existing
    from public.project_l_adaptive_memory_counterfactual_executions
    where user_id=p_user
      and request_id=v_request_id;

    if not found then
      raise exception 'PROJECT_L_LAYER304_DUPLICATE_LOOKUP_FAILED';
    end if;

    if v_existing.activation_generation<>v_sampling.activation_generation
       or v_existing.terminal_status<>v_status then
      raise exception 'PROJECT_L_LAYER304_EXECUTION_REPLAY_MISMATCH';
    end if;

    return jsonb_build_object(
      'status','already_recorded',
      'recorded',false,
      'executionId',v_existing.id,
      'terminalStatus',v_existing.terminal_status,
      'durationMs',v_existing.duration_ms,
      'generation',v_existing.activation_generation
    );
  end if;

  return jsonb_build_object(
    'status','recorded',
    'recorded',true,
    'executionId',v_id,
    'terminalStatus',v_status,
    'durationMs',v_duration,
    'generation',v_sampling.activation_generation
  );
end;
$$;

revoke all on function public.project_l_record_adaptive_counterfactual_execution_v1(
  uuid,text,text,numeric,text,timestamptz
) from public, anon, authenticated;

grant execute on function public.project_l_record_adaptive_counterfactual_execution_v1(
  uuid,text,text,numeric,text,timestamptz
) to service_role;

create or replace function public.project_l_adaptive_counterfactual_reliability_v1(
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
  v_admitted integer := 0;
  v_terminal integer := 0;
  v_completed integer := 0;
  v_timed_out integer := 0;
  v_failed integer := 0;
  v_missing integer := 0;
  v_terminal_coverage numeric := 0;
  v_completion_rate numeric := 0;
  v_timeout_share numeric := 0;
  v_failure_share numeric := 0;
  v_max_completed_ms numeric := 0;
  v_avg_completed_ms numeric := 0;
  v_certified boolean := false;
  v_missing_requirements jsonb;
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

  if v_generation is null or v_generation<1 then
    return jsonb_build_object(
      'available',true,
      'certified',false,
      'generation',v_generation,
      'reason','shadow_generation_missing'
    );
  end if;

  select count(*)
  into v_admitted
  from public.project_l_adaptive_memory_counterfactual_sampling
  where activation_generation=v_generation
    and admitted=true
    and observed_at<=p_now;

  select
    count(*),
    count(*) filter (where terminal_status='completed'),
    count(*) filter (where terminal_status='timed_out'),
    count(*) filter (where terminal_status='failed'),
    max(duration_ms) filter (where terminal_status='completed'),
    avg(duration_ms) filter (where terminal_status='completed')
  into
    v_terminal,
    v_completed,
    v_timed_out,
    v_failed,
    v_max_completed_ms,
    v_avg_completed_ms
  from public.project_l_adaptive_memory_counterfactual_executions
  where activation_generation=v_generation
    and observed_at<=p_now;

  v_missing := greatest(0,v_admitted-v_terminal);

  if v_admitted>0 then
    v_terminal_coverage := round(v_terminal::numeric/v_admitted::numeric,6);
    v_completion_rate := round(v_completed::numeric/v_admitted::numeric,6);
    v_timeout_share := round(v_timed_out::numeric/v_admitted::numeric,6);
    v_failure_share := round(v_failed::numeric/v_admitted::numeric,6);
  end if;

  v_max_completed_ms := round(coalesce(v_max_completed_ms,0),3);
  v_avg_completed_ms := round(coalesce(v_avg_completed_ms,0),3);

  v_certified :=
    v_admitted>=10
    and v_terminal_coverage>=0.85
    and v_completion_rate>=0.75
    and v_timeout_share<=0.15
    and v_failure_share<=0.15
    and v_max_completed_ms<=1500;

  select coalesce(jsonb_agg(name order by name),'[]'::jsonb)
  into v_missing_requirements
  from (
    values
      ('counterfactual_admissions_10',v_admitted>=10),
      ('counterfactual_terminal_coverage_85pct',v_terminal_coverage>=0.85),
      ('counterfactual_completion_rate_75pct',v_completion_rate>=0.75),
      ('counterfactual_timeout_share_max_15pct',v_timeout_share<=0.15),
      ('counterfactual_failure_share_max_15pct',v_failure_share<=0.15),
      ('counterfactual_completed_max_1500ms',v_max_completed_ms<=1500)
  ) as requirements(name,ready)
  where not ready;

  return jsonb_build_object(
    'available',true,
    'version','layer304-v1',
    'certified',v_certified,
    'generation',v_generation,
    'requirements',jsonb_build_object(
      'minimumAdmissions',10,
      'minimumTerminalCoverage',0.85,
      'minimumCompletionRate',0.75,
      'maximumTimeoutShare',0.15,
      'maximumFailureShare',0.15,
      'maximumCompletedDurationMs',1500,
      'backgroundEvidenceDeadlineMs',1200
    ),
    'observed',jsonb_build_object(
      'admitted',v_admitted,
      'terminal',v_terminal,
      'completed',v_completed,
      'timedOut',v_timed_out,
      'failed',v_failed,
      'missingTerminalReceipts',v_missing,
      'terminalCoverage',v_terminal_coverage,
      'completionRate',v_completion_rate,
      'timeoutShare',v_timeout_share,
      'failureShare',v_failure_share,
      'maximumCompletedDurationMs',v_max_completed_ms,
      'averageCompletedDurationMs',v_avg_completed_ms
    ),
    'missing',v_missing_requirements,
    'reason',case
      when v_certified then 'counterfactual_execution_reliable'
      else 'counterfactual_execution_reliability_incomplete'
    end
  );
end;
$$;

revoke all on function public.project_l_adaptive_counterfactual_reliability_v1(
  bigint,timestamptz
) from public, anon, authenticated;

grant execute on function public.project_l_adaptive_counterfactual_reliability_v1(
  bigint,timestamptz
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
  v_304_record boolean :=
    to_regprocedure('public.project_l_record_adaptive_counterfactual_execution_v1(uuid,text,text,numeric,text,timestamptz)') is not null;
  v_304_cert boolean :=
    to_regprocedure('public.project_l_adaptive_counterfactual_reliability_v1(bigint,timestamptz)') is not null;

  v_adaptation_table boolean := to_regclass('public.project_l_retrieval_adaptation_events') is not null;
  v_lease_table boolean := to_regclass('public.project_l_retrieval_strategy_leases') is not null;
  v_outcome_table boolean := to_regclass('public.project_l_retrieval_served_outcomes') is not null;
  v_query_binding_table boolean := to_regclass('public.project_l_retrieval_outcome_query_bindings') is not null;
  v_cohort_binding_table boolean := to_regclass('public.project_l_retrieval_outcome_cohort_bindings') is not null;
  v_shadow_table boolean := to_regclass('public.project_l_adaptive_memory_shadow_observations') is not null;
  v_counterfactual_table boolean := to_regclass('public.project_l_adaptive_memory_shadow_counterfactuals') is not null;
  v_sampling_table boolean := to_regclass('public.project_l_adaptive_memory_counterfactual_sampling') is not null;
  v_execution_table boolean := to_regclass('public.project_l_adaptive_memory_counterfactual_executions') is not null;

  v_adaptation_rls boolean := false;
  v_lease_rls boolean := false;
  v_outcome_rls boolean := false;
  v_query_binding_rls boolean := false;
  v_cohort_binding_rls boolean := false;
  v_shadow_rls boolean := false;
  v_counterfactual_rls boolean := false;
  v_sampling_rls boolean := false;
  v_execution_rls boolean := false;

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

  select coalesce(c.relrowsecurity,false)
  into v_execution_rls
  from pg_catalog.pg_class c join pg_catalog.pg_namespace n on n.oid=c.relnamespace
  where n.nspname='public' and c.relname='project_l_adaptive_memory_counterfactual_executions';

  v_stack_ready :=
    v_293 and v_294 and v_295
    and v_296_record and v_296_feed
    and v_297 and v_298
    and v_299_record and v_299_feed
    and v_301_record and v_301_cert
    and v_302_score and v_302_record and v_302_cert
    and v_303_admission and v_303_status
    and v_304_record and v_304_cert
    and v_adaptation_table and coalesce(v_adaptation_rls,false)
    and v_lease_table and coalesce(v_lease_rls,false)
    and v_outcome_table and coalesce(v_outcome_rls,false)
    and v_query_binding_table and coalesce(v_query_binding_rls,false)
    and v_cohort_binding_table and coalesce(v_cohort_binding_rls,false)
    and v_shadow_table and coalesce(v_shadow_rls,false)
    and v_counterfactual_table and coalesce(v_counterfactual_rls,false)
    and v_sampling_table and coalesce(v_sampling_rls,false)
    and v_execution_table and coalesce(v_execution_rls,false);

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
      ('layer304_execution_recorder',v_304_record),
      ('layer304_reliability_certificate',v_304_cert),
      ('adaptation_table_rls',v_adaptation_table and coalesce(v_adaptation_rls,false)),
      ('lease_table_rls',v_lease_table and coalesce(v_lease_rls,false)),
      ('outcome_table_rls',v_outcome_table and coalesce(v_outcome_rls,false)),
      ('query_binding_table_rls',v_query_binding_table and coalesce(v_query_binding_rls,false)),
      ('cohort_binding_table_rls',v_cohort_binding_table and coalesce(v_cohort_binding_rls,false)),
      ('shadow_observation_table_rls',v_shadow_table and coalesce(v_shadow_rls,false)),
      ('shadow_counterfactual_table_rls',v_counterfactual_table and coalesce(v_counterfactual_rls,false)),
      ('counterfactual_sampling_table_rls',v_sampling_table and coalesce(v_sampling_rls,false)),
      ('counterfactual_execution_table_rls',v_execution_table and coalesce(v_execution_rls,false))
  ) as checks(name,ready)
  where not ready;

  return jsonb_build_object(
    'version','layer304-v1',
    'requiredLayerFloor',304,
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
  v_reliability_cert jsonb;
  v_stack_ready boolean := false;
  v_shadow_certified boolean := false;
  v_counter_certified boolean := false;
  v_reliability_certified boolean := false;
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

  v_reliability_cert := public.project_l_adaptive_counterfactual_reliability_v1(
    v_basis_generation,
    now()
  );
  v_reliability_certified :=
    coalesce((v_reliability_cert->>'certified')::boolean,false);

  v_runtime_enabled :=
    v_cfg.mode='active'
    and v_stack_ready
    and v_shadow_certified
    and v_counter_certified
    and v_reliability_certified;

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
    'counterfactualReliabilityCertified',v_reliability_certified,
    'shadowCertification',v_shadow_cert,
    'counterfactualCertification',v_counter_cert,
    'counterfactualReliability',v_reliability_cert,
    'generation',v_cfg.generation,
    'activationBasisShadowGeneration',v_cfg.activation_basis_shadow_generation,
    'requiredLayerFloor',304,
    'reason',case
      when v_cfg.mode='active' and not v_stack_ready
        then 'configured_active_but_stack_unhealthy'
      when v_cfg.mode='active' and not v_shadow_certified
        then 'configured_active_but_shadow_uncertified'
      when v_cfg.mode='active' and not v_counter_certified
        then 'configured_active_but_counterfactual_uncertified'
      when v_cfg.mode='active' and not v_reliability_certified
        then 'configured_active_but_counterfactual_unreliable'
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
  v_reliability_cert jsonb;
  v_stack_ready boolean := false;
  v_shadow_certified boolean := false;
  v_counter_certified boolean := false;
  v_reliability_certified boolean := false;
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
    pg_catalog.hashtextextended('project_l_adaptive_memory_activation',304)
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

  v_reliability_cert := public.project_l_adaptive_counterfactual_reliability_v1(
    v_cfg.generation,
    p_now
  );
  v_reliability_certified :=
    coalesce((v_reliability_cert->>'certified')::boolean,false);

  if v_mode='active' and v_cfg.mode<>'shadow_only' then
    return jsonb_build_object(
      'status','blocked',
      'changed',false,
      'configuredMode',v_cfg.mode,
      'generation',v_cfg.generation,
      'reason','activation_requires_shadow_only_prestate',
      'stackHealth',v_health,
      'shadowCertification',v_shadow_cert,
      'counterfactualCertification',v_counter_cert,
      'counterfactualReliability',v_reliability_cert
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
      'counterfactualCertification',v_counter_cert,
      'counterfactualReliability',v_reliability_cert
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
      'counterfactualCertification',v_counter_cert,
      'counterfactualReliability',v_reliability_cert
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
      'counterfactualCertification',v_counter_cert,
      'counterfactualReliability',v_reliability_cert
    );
  end if;

  if v_mode='active' and not v_reliability_certified then
    return jsonb_build_object(
      'status','blocked',
      'changed',false,
      'configuredMode',v_cfg.mode,
      'generation',v_cfg.generation,
      'reason','activation_requires_counterfactual_reliability',
      'stackHealth',v_health,
      'shadowCertification',v_shadow_cert,
      'counterfactualCertification',v_counter_cert,
      'counterfactualReliability',v_reliability_cert
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
      'counterfactualCertification',v_counter_cert,
      'counterfactualReliability',v_reliability_cert
    );
  end if;

  v_new_generation := v_cfg.generation+1;

  update public.project_l_adaptive_memory_activation
  set
    mode=v_mode,
    generation=v_new_generation,
    required_layer_floor=304,
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
      'counterfactualCertification',v_counter_cert,
      'counterfactualReliability',v_reliability_cert
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
      and v_counter_certified
      and v_reliability_certified,
    'activationBasisShadowGeneration',
      case when v_mode='active' then v_cfg.generation else null end,
    'stackHealth',v_health,
    'shadowCertification',v_shadow_cert,
    'counterfactualCertification',v_counter_cert
  );
end;
$$;



comment on table public.project_l_adaptive_memory_counterfactual_executions is
  'Layer 304 append-only terminal execution receipts for admitted background counterfactual work; no query or memory content is stored.';

comment on function public.project_l_record_adaptive_counterfactual_execution_v1(
  uuid,text,text,numeric,text,timestamptz
) is
  'Layer 304 terminal execution receipt recorder. COMPLETED requires the Layer 302 quality receipt and must remain within the accepted deadline envelope.';

comment on function public.project_l_adaptive_counterfactual_reliability_v1(
  bigint,timestamptz
) is
  'Layer 304 reliability certificate over admitted shadow counterfactual reservations, including completion, timeout, failure and missing-receipt rates.';

comment on function public.project_l_adaptive_memory_stack_health_v1() is
  'Layers 300-304 stack health: adaptive activation requires background-isolated counterfactual execution and reliability certification.';

comment on function public.project_l_adaptive_memory_activation_status_v1() is
  'Layers 300-304 activation status: ACTIVE requires stack health, burn-in, counterfactual quality, and counterfactual execution reliability.';

comment on function public.project_l_set_adaptive_memory_activation_v1(
  text,text,bigint,timestamptz
) is
  'Layers 300-304 activation control: required layer floor 304 and counterfactual reliability certification before ACTIVE.';
