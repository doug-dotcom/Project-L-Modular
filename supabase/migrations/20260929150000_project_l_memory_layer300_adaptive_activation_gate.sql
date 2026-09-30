-- Project L Memory Layer 300 — Adaptive Memory Activation Gate
--
-- Milestone boundary for the Layers 293-299 adaptive retrieval loop.
--
-- The adaptive loop is shadow-only by default. Learned strategy influence may
-- reach runtime only when:
--   * configuration is explicitly set to ACTIVE;
--   * every required Layer 293-299 database object is present;
--   * the activation change used the current generation (compare-and-swap);
--   * activation came from SHADOW_ONLY, never directly from DISABLED.
--
-- If health later degrades, ACTIVE configuration automatically fails closed to
-- effective SHADOW_ONLY behaviour without mutating the configured state.

create table if not exists public.project_l_adaptive_memory_activation (
  id text primary key default 'global'
    check (id = 'global'),
  mode text not null default 'shadow_only'
    check (mode in ('disabled','shadow_only','active')),
  generation bigint not null default 1
    check (generation >= 1),
  required_layer_floor integer not null default 299
    check (required_layer_floor >= 299),
  reason text not null default 'layer300_default_shadow_only',
  enabled_at timestamptz,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);

insert into public.project_l_adaptive_memory_activation(
  id,mode,generation,required_layer_floor,reason
)
values (
  'global','shadow_only',1,299,'layer300_default_shadow_only'
)
on conflict (id) do nothing;

alter table public.project_l_adaptive_memory_activation
  enable row level security;

revoke all on table public.project_l_adaptive_memory_activation
  from public, anon, authenticated;

grant select, update on table public.project_l_adaptive_memory_activation
  to service_role;

create table if not exists public.project_l_adaptive_memory_activation_events (
  id uuid primary key default gen_random_uuid(),
  previous_mode text not null
    check (previous_mode in ('disabled','shadow_only','active')),
  new_mode text not null
    check (new_mode in ('disabled','shadow_only','active')),
  previous_generation bigint not null,
  new_generation bigint not null,
  reason text not null,
  stack_snapshot jsonb not null default '{}'::jsonb,
  changed_at timestamptz not null default now()
);

create index if not exists project_l_adaptive_memory_activation_events_created_idx
  on public.project_l_adaptive_memory_activation_events(changed_at desc,id desc);

alter table public.project_l_adaptive_memory_activation_events
  enable row level security;

revoke all on table public.project_l_adaptive_memory_activation_events
  from public, anon, authenticated;

grant select, insert on table public.project_l_adaptive_memory_activation_events
  to service_role;

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

  v_adaptation_rls boolean := false;
  v_lease_rls boolean := false;
  v_outcome_rls boolean := false;
  v_query_binding_rls boolean := false;
  v_cohort_binding_rls boolean := false;

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

  v_stack_ready :=
    v_293 and v_294 and v_295
    and v_296_record and v_296_feed
    and v_297 and v_298
    and v_299_record and v_299_feed
    and v_adaptation_table and coalesce(v_adaptation_rls,false)
    and v_lease_table and coalesce(v_lease_rls,false)
    and v_outcome_table and coalesce(v_outcome_rls,false)
    and v_query_binding_table and coalesce(v_query_binding_rls,false)
    and v_cohort_binding_table and coalesce(v_cohort_binding_rls,false);

  select coalesce(
    jsonb_agg(name order by name),
    '[]'::jsonb
  )
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
      ('adaptation_table_rls',v_adaptation_table and coalesce(v_adaptation_rls,false)),
      ('lease_table_rls',v_lease_table and coalesce(v_lease_rls,false)),
      ('outcome_table_rls',v_outcome_table and coalesce(v_outcome_rls,false)),
      ('query_binding_table_rls',v_query_binding_table and coalesce(v_query_binding_rls,false)),
      ('cohort_binding_table_rls',v_cohort_binding_table and coalesce(v_cohort_binding_rls,false))
  ) as checks(name,ready)
  where not ready;

  return jsonb_build_object(
    'version','layer300-v1',
    'requiredLayerFloor',299,
    'stackReady',v_stack_ready,
    'missing',v_missing,
    'components',jsonb_build_object(
      'layer293Guard',v_293,
      'layer294LeaseEvaluator',v_294,
      'layer295RuntimeSelector',v_295,
      'layer296OutcomeRecorder',v_296_record,
      'layer296OutcomeFeed',v_296_feed,
      'layer297GovernedEvaluator',v_297,
      'layer298ExactBinding',v_298,
      'layer299CohortRecorder',v_299_record,
      'layer299CohortFeed',v_299_feed,
      'adaptationTableRls',v_adaptation_table and coalesce(v_adaptation_rls,false),
      'leaseTableRls',v_lease_table and coalesce(v_lease_rls,false),
      'outcomeTableRls',v_outcome_table and coalesce(v_outcome_rls,false),
      'queryBindingTableRls',v_query_binding_table and coalesce(v_query_binding_rls,false),
      'cohortBindingTableRls',v_cohort_binding_table and coalesce(v_cohort_binding_rls,false)
    )
  );
end;
$$;

revoke all on function public.project_l_adaptive_memory_stack_health_v1()
  from public, anon, authenticated;

grant execute on function public.project_l_adaptive_memory_stack_health_v1()
  to service_role;

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
  v_stack_ready boolean := false;
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
      'generation',null,
      'reason','activation_config_missing'
    );
  end if;

  v_health := public.project_l_adaptive_memory_stack_health_v1();
  v_stack_ready := coalesce((v_health->>'stackReady')::boolean,false);

  v_runtime_enabled :=
    v_cfg.mode='active'
    and v_stack_ready;

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
    'generation',v_cfg.generation,
    'requiredLayerFloor',v_cfg.required_layer_floor,
    'reason',case
      when v_cfg.mode='active' and not v_stack_ready
        then 'configured_active_but_stack_unhealthy'
      else v_cfg.reason
    end,
    'enabledAt',v_cfg.enabled_at,
    'updatedAt',v_cfg.updated_at,
    'stackHealth',v_health
  );
end;
$$;

revoke all on function public.project_l_adaptive_memory_activation_status_v1()
  from public, anon, authenticated;

grant execute on function public.project_l_adaptive_memory_activation_status_v1()
  to service_role;

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
  v_stack_ready boolean := false;
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
    pg_catalog.hashtextextended('project_l_adaptive_memory_activation',300)
  );

  select *
  into v_cfg
  from public.project_l_adaptive_memory_activation
  where id='global'
  for update;

  if not found then
    raise exception 'PROJECT_L_LAYER300_CONFIG_MISSING';
  end if;

  if v_cfg.generation <> p_expected_generation then
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

  if v_mode='active' and v_cfg.mode<>'shadow_only' then
    return jsonb_build_object(
      'status','blocked',
      'changed',false,
      'configuredMode',v_cfg.mode,
      'generation',v_cfg.generation,
      'reason','activation_requires_shadow_only_prestate',
      'stackHealth',v_health
    );
  end if;

  if v_mode='active' and not v_stack_ready then
    return jsonb_build_object(
      'status','blocked',
      'changed',false,
      'configuredMode',v_cfg.mode,
      'generation',v_cfg.generation,
      'reason','activation_requires_healthy_stack',
      'stackHealth',v_health
    );
  end if;

  if v_mode=v_cfg.mode then
    return jsonb_build_object(
      'status','already_set',
      'changed',false,
      'configuredMode',v_cfg.mode,
      'generation',v_cfg.generation,
      'stackHealth',v_health
    );
  end if;

  v_new_generation := v_cfg.generation+1;

  update public.project_l_adaptive_memory_activation
  set
    mode=v_mode,
    generation=v_new_generation,
    reason=v_reason,
    enabled_at=case when v_mode='active' then p_now else null end,
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
    v_health,
    p_now
  );

  return jsonb_build_object(
    'status','changed',
    'changed',true,
    'previousMode',v_cfg.mode,
    'configuredMode',v_mode,
    'previousGeneration',v_cfg.generation,
    'generation',v_new_generation,
    'runtimeInfluenceEnabled',v_mode='active' and v_stack_ready,
    'stackHealth',v_health
  );
end;
$$;

revoke all on function public.project_l_set_adaptive_memory_activation_v1(
  text,text,bigint,timestamptz
) from public, anon, authenticated;

grant execute on function public.project_l_set_adaptive_memory_activation_v1(
  text,text,bigint,timestamptz
) to service_role;

comment on table public.project_l_adaptive_memory_activation is
  'Layer 300 master activation gate for the Project L adaptive retrieval loop. Defaults to shadow_only and automatically fails closed when stack health is incomplete.';

comment on function public.project_l_adaptive_memory_stack_health_v1() is
  'Layer 300 read-only health certificate for required Layers 293-299 database objects and RLS boundaries.';

comment on function public.project_l_adaptive_memory_activation_status_v1() is
  'Layer 300 effective activation status. ACTIVE configuration influences runtime only while the complete adaptive stack is healthy.';

comment on function public.project_l_set_adaptive_memory_activation_v1(
  text,text,bigint,timestamptz
) is
  'Layer 300 compare-and-swap activation control with audited transitions and mandatory shadow-only prestate before ACTIVE.';
