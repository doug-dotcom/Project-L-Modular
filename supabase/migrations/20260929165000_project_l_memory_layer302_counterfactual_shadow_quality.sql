-- Project L Memory Layer 302 — Counterfactual Shadow Quality
--
-- Layer 301 proves the adaptive selector behaves consistently in shadow.
-- Layer 302 proves that mode-changing shadow proposals are actually better.
--
-- During SHADOW_ONLY, when the learned proposal differs from the served mode,
-- l-companion may execute the proposed retrieval path without using it in the
-- answer. Only content-free retrieval quality metrics are persisted.
--
-- ACTIVE now additionally requires a current-generation counterfactual quality
-- certificate:
--   * >=10 successful mode-changing comparisons;
--   * comparisons across >=3 UTC days;
--   * >=6 keyed exact queries;
--   * >=4 keyed lexical cohorts;
--   * >=70% of proposed paths beat the served path;
--   * mean proposed advantage >=0.08;
--   * mean proposed score >=0.65;
--   * <=20% materially bad losses (advantage <= -0.10).
--
-- Counterfactual evidence is generation-bound, append-only, content-free, and
-- cannot itself promote a new learned strategy.

create table if not exists public.project_l_adaptive_memory_shadow_counterfactuals (
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
  actual_score numeric not null
    check (actual_score between 0 and 1),
  proposed_score numeric not null
    check (proposed_score between 0 and 1),
  advantage numeric not null
    check (advantage between -1 and 1),
  proposed_won boolean not null,
  material_loss boolean not null,
  actual_metrics jsonb not null default '{}'::jsonb,
  proposed_metrics jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null,
  created_at timestamptz not null default now(),
  unique(user_id,request_id)
);

create index if not exists project_l_shadow_counterfactuals_generation_idx
  on public.project_l_adaptive_memory_shadow_counterfactuals(
    activation_generation,
    observed_at desc,
    id desc
  );

create index if not exists project_l_shadow_counterfactuals_cohort_idx
  on public.project_l_adaptive_memory_shadow_counterfactuals(
    activation_generation,
    query_cohort_fingerprint,
    observed_at desc
  );

alter table public.project_l_adaptive_memory_shadow_counterfactuals
  enable row level security;

revoke all on table public.project_l_adaptive_memory_shadow_counterfactuals
  from public, anon, authenticated;

grant select, insert on table public.project_l_adaptive_memory_shadow_counterfactuals
  to service_role;

create or replace function public.project_l_retrieval_proxy_score_v1(
  p_metrics jsonb
)
returns numeric
language plpgsql
stable
security invoker
set search_path = ''
set statement_timeout = '5s'
as $$
declare
  v_returned integer := 0;
  v_safe integer := 0;
  v_corr integer := 0;
  v_needs integer := 0;
  v_subjects integer := 0;
  v_diversity_fallback boolean := false;
  v_retrieval_fallback boolean := false;
  v_safe_ratio numeric := 0;
  v_corr_ratio numeric := 0;
  v_needs_ratio numeric := 0;
  v_diversity_ratio numeric := 0;
  v_score numeric := 0.10;
begin
  if p_metrics is null or jsonb_typeof(p_metrics)<>'object' then
    raise exception 'PROJECT_L_LAYER302_METRICS_OBJECT_REQUIRED';
  end if;

  if octet_length(p_metrics::text)>8000 then
    raise exception 'PROJECT_L_LAYER302_METRICS_TOO_LARGE';
  end if;

  if coalesce(p_metrics->>'returned_count','') ~ '^[0-9]+$' then
    v_returned := least((p_metrics->>'returned_count')::integer,1000);
  end if;
  if coalesce(p_metrics->>'safe_assertion_count','') ~ '^[0-9]+$' then
    v_safe := least((p_metrics->>'safe_assertion_count')::integer,1000);
  end if;
  if coalesce(p_metrics->>'corroborated_count','') ~ '^[0-9]+$' then
    v_corr := least((p_metrics->>'corroborated_count')::integer,1000);
  end if;
  if coalesce(p_metrics->>'needs_corroboration_count','') ~ '^[0-9]+$' then
    v_needs := least((p_metrics->>'needs_corroboration_count')::integer,1000);
  end if;
  if coalesce(p_metrics->>'unique_subject_count','') ~ '^[0-9]+$' then
    v_subjects := least((p_metrics->>'unique_subject_count')::integer,1000);
  end if;

  v_diversity_fallback :=
    lower(coalesce(p_metrics->>'diversity_fallback_used','false'))
      in ('true','1','yes');
  v_retrieval_fallback :=
    lower(coalesce(p_metrics->>'retrieval_fallback_used','false'))
      in ('true','1','yes');

  if v_returned>0 then
    v_safe_ratio :=
      least(v_safe,v_returned)::numeric/v_returned::numeric;
    v_corr_ratio :=
      least(v_corr,v_returned)::numeric/v_returned::numeric;
    v_needs_ratio :=
      least(v_needs,v_returned)::numeric/v_returned::numeric;
    v_diversity_ratio :=
      least(
        1::numeric,
        v_subjects::numeric/greatest(1,least(v_returned,4))::numeric
      );

    -- Intentionally identical to Layer 296 deterministic_retrieval_proxy_v1.
    v_score :=
      0.25
      + (0.35*v_safe_ratio)
      + (0.20*v_corr_ratio)
      + (0.10*v_diversity_ratio)
      + case when not v_diversity_fallback then 0.10 else 0 end
      - (0.20*v_needs_ratio)
      - case when v_retrieval_fallback then 0.05 else 0 end;

    v_score := round(least(0.95,greatest(0.05,v_score)),6);
  end if;

  return v_score;
end;
$$;

revoke all on function public.project_l_retrieval_proxy_score_v1(jsonb)
  from public, anon, authenticated;

grant execute on function public.project_l_retrieval_proxy_score_v1(jsonb)
  to service_role;

create or replace function public.project_l_adaptive_counterfactual_certification_v1(
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

  v_comparisons integer := 0;
  v_distinct_days integer := 0;
  v_distinct_queries integer := 0;
  v_distinct_cohorts integer := 0;
  v_wins integer := 0;
  v_material_losses integer := 0;
  v_win_rate numeric := 0;
  v_material_loss_share numeric := 0;
  v_actual_avg numeric;
  v_proposed_avg numeric;
  v_advantage_avg numeric;
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

  if v_generation is null or v_generation<1 then
    return jsonb_build_object(
      'available',true,
      'certified',false,
      'generation',v_generation,
      'reason','shadow_generation_missing'
    );
  end if;

  v_shadow_started_at := v_cfg.shadow_started_at;

  select
    count(*),
    count(distinct ((observed_at at time zone 'UTC')::date)),
    count(distinct query_fingerprint),
    count(distinct query_cohort_fingerprint),
    count(*) filter (where proposed_won),
    count(*) filter (where material_loss),
    avg(actual_score),
    avg(proposed_score),
    avg(advantage),
    min(observed_at),
    max(observed_at)
  into
    v_comparisons,
    v_distinct_days,
    v_distinct_queries,
    v_distinct_cohorts,
    v_wins,
    v_material_losses,
    v_actual_avg,
    v_proposed_avg,
    v_advantage_avg,
    v_first_observed_at,
    v_last_observed_at
  from public.project_l_adaptive_memory_shadow_counterfactuals
  where activation_generation=v_generation
    and (
      v_shadow_started_at is null
      or observed_at>=v_shadow_started_at
    )
    and observed_at<=p_now;

  if v_comparisons>0 then
    v_win_rate :=
      round(v_wins::numeric/v_comparisons::numeric,6);
    v_material_loss_share :=
      round(v_material_losses::numeric/v_comparisons::numeric,6);
  end if;

  v_certified :=
    v_comparisons>=10
    and v_distinct_days>=3
    and v_distinct_queries>=6
    and v_distinct_cohorts>=4
    and v_win_rate>=0.70
    and coalesce(v_advantage_avg,0)>=0.08
    and coalesce(v_proposed_avg,0)>=0.65
    and v_material_loss_share<=0.20;

  select coalesce(jsonb_agg(name order by name),'[]'::jsonb)
  into v_missing
  from (
    values
      ('counterfactual_comparisons_10',v_comparisons>=10),
      ('counterfactual_distinct_days_3',v_distinct_days>=3),
      ('counterfactual_exact_queries_6',v_distinct_queries>=6),
      ('counterfactual_lexical_cohorts_4',v_distinct_cohorts>=4),
      ('counterfactual_win_rate_70pct',v_win_rate>=0.70),
      ('counterfactual_mean_advantage_008',coalesce(v_advantage_avg,0)>=0.08),
      ('counterfactual_proposed_average_065',coalesce(v_proposed_avg,0)>=0.65),
      ('counterfactual_material_loss_share_max_20pct',v_material_loss_share<=0.20)
  ) as requirements(name,ready)
  where not ready;

  return jsonb_build_object(
    'available',true,
    'version','layer302-v1',
    'certified',v_certified,
    'generation',v_generation,
    'requirements',jsonb_build_object(
      'minimumComparisons',10,
      'minimumDistinctDays',3,
      'minimumDistinctExactQueries',6,
      'minimumDistinctLexicalCohorts',4,
      'minimumWinRate',0.70,
      'minimumMeanAdvantage',0.08,
      'minimumProposedAverageScore',0.65,
      'maximumMaterialLossShare',0.20,
      'materialLossThreshold',-0.10
    ),
    'observed',jsonb_build_object(
      'comparisons',v_comparisons,
      'distinctDays',v_distinct_days,
      'distinctExactQueries',v_distinct_queries,
      'distinctLexicalCohorts',v_distinct_cohorts,
      'wins',v_wins,
      'winRate',v_win_rate,
      'materialLosses',v_material_losses,
      'materialLossShare',v_material_loss_share,
      'actualAverageScore',round(coalesce(v_actual_avg,0),6),
      'proposedAverageScore',round(coalesce(v_proposed_avg,0),6),
      'meanAdvantage',round(coalesce(v_advantage_avg,0),6),
      'firstObservedAt',v_first_observed_at,
      'lastObservedAt',v_last_observed_at
    ),
    'missing',v_missing,
    'reason',case
      when v_certified then 'counterfactual_shadow_quality_certified'
      else 'counterfactual_shadow_quality_incomplete'
    end
  );
end;
$$;

revoke all on function public.project_l_adaptive_counterfactual_certification_v1(
  bigint,timestamptz
) from public, anon, authenticated;

grant execute on function public.project_l_adaptive_counterfactual_certification_v1(
  bigint,timestamptz
) to service_role;

create or replace function public.project_l_record_adaptive_shadow_counterfactual_v1(
  p_user uuid,
  p_request_id text,
  p_intent text,
  p_query_fingerprint text,
  p_query_cohort_fingerprint text,
  p_actual_mode text,
  p_proposed_mode text,
  p_proposal_source text,
  p_proposal_reason text,
  p_actual_metrics jsonb,
  p_proposed_metrics jsonb,
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
  v_actual_mode text := lower(btrim(coalesce(p_actual_mode,'')));
  v_proposed_mode text := lower(btrim(coalesce(p_proposed_mode,'')));
  v_source text := left(btrim(coalesce(p_proposal_source,'')),80);
  v_reason text :=
    nullif(left(btrim(coalesce(p_proposal_reason,'')),240),'');
  v_status jsonb;
  v_generation bigint;
  v_actual_score numeric;
  v_proposed_score numeric;
  v_advantage numeric;
  v_id uuid;
  v_existing public.project_l_adaptive_memory_shadow_counterfactuals%rowtype;
begin
  if p_user is null then
    raise exception 'PROJECT_L_LAYER302_USER_REQUIRED';
  end if;
  if v_request_id='' then
    raise exception 'PROJECT_L_LAYER302_REQUEST_ID_REQUIRED';
  end if;
  if v_intent='' then
    raise exception 'PROJECT_L_LAYER302_INTENT_REQUIRED';
  end if;
  if v_query_fingerprint !~ '^[0-9a-f]{64}$' then
    raise exception 'PROJECT_L_LAYER302_INVALID_QUERY_FINGERPRINT';
  end if;
  if v_cohort_fingerprint !~ '^[0-9a-f]{64}$' then
    raise exception 'PROJECT_L_LAYER302_INVALID_COHORT_FINGERPRINT';
  end if;
  if v_actual_mode not in ('lexical','semantic','hybrid')
     or v_proposed_mode not in ('lexical','semantic','hybrid') then
    raise exception 'PROJECT_L_LAYER302_INVALID_MODE';
  end if;
  if v_actual_mode=v_proposed_mode then
    return jsonb_build_object(
      'status','ignored',
      'recorded',false,
      'reason','counterfactual_requires_mode_change'
    );
  end if;
  if v_source='' then
    raise exception 'PROJECT_L_LAYER302_PROPOSAL_SOURCE_REQUIRED';
  end if;
  if coalesce(p_explicit_mode_used,false) then
    return jsonb_build_object(
      'status','ignored',
      'recorded',false,
      'reason','explicit_request_not_counterfactual_evidence'
    );
  end if;

  v_status := public.project_l_adaptive_memory_activation_status_v1();

  if coalesce(v_status->>'effectiveMode','shadow_only')<>'shadow_only'
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

  if v_generation is null or v_generation<1 then
    return jsonb_build_object(
      'status','ignored',
      'recorded',false,
      'reason','activation_generation_missing'
    );
  end if;

  v_actual_score := public.project_l_retrieval_proxy_score_v1(p_actual_metrics);
  v_proposed_score := public.project_l_retrieval_proxy_score_v1(p_proposed_metrics);
  v_advantage := round((v_proposed_score-v_actual_score)::numeric,6);

  insert into public.project_l_adaptive_memory_shadow_counterfactuals(
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
    actual_score,
    proposed_score,
    advantage,
    proposed_won,
    material_loss,
    actual_metrics,
    proposed_metrics,
    observed_at
  )
  values (
    p_user,
    v_request_id,
    v_generation,
    v_intent,
    v_query_fingerprint,
    v_cohort_fingerprint,
    v_actual_mode,
    v_proposed_mode,
    v_source,
    v_reason,
    v_actual_score,
    v_proposed_score,
    v_advantage,
    v_advantage>0,
    v_advantage<=-0.10,
    jsonb_build_object(
      'returned_count',coalesce(p_actual_metrics->'returned_count','0'::jsonb),
      'safe_assertion_count',coalesce(p_actual_metrics->'safe_assertion_count','0'::jsonb),
      'corroborated_count',coalesce(p_actual_metrics->'corroborated_count','0'::jsonb),
      'needs_corroboration_count',coalesce(p_actual_metrics->'needs_corroboration_count','0'::jsonb),
      'unique_subject_count',coalesce(p_actual_metrics->'unique_subject_count','0'::jsonb),
      'diversity_fallback_used',coalesce(p_actual_metrics->'diversity_fallback_used','false'::jsonb),
      'retrieval_fallback_used',coalesce(p_actual_metrics->'retrieval_fallback_used','false'::jsonb)
    ),
    jsonb_build_object(
      'returned_count',coalesce(p_proposed_metrics->'returned_count','0'::jsonb),
      'safe_assertion_count',coalesce(p_proposed_metrics->'safe_assertion_count','0'::jsonb),
      'corroborated_count',coalesce(p_proposed_metrics->'corroborated_count','0'::jsonb),
      'needs_corroboration_count',coalesce(p_proposed_metrics->'needs_corroboration_count','0'::jsonb),
      'unique_subject_count',coalesce(p_proposed_metrics->'unique_subject_count','0'::jsonb),
      'diversity_fallback_used',coalesce(p_proposed_metrics->'diversity_fallback_used','false'::jsonb),
      'retrieval_fallback_used',coalesce(p_proposed_metrics->'retrieval_fallback_used','false'::jsonb)
    ),
    p_observed_at
  )
  on conflict (user_id,request_id) do nothing
  returning id into v_id;

  if v_id is null then
    select *
    into v_existing
    from public.project_l_adaptive_memory_shadow_counterfactuals
    where user_id=p_user
      and request_id=v_request_id;

    if not found then
      raise exception 'PROJECT_L_LAYER302_DUPLICATE_LOOKUP_FAILED';
    end if;

    if v_existing.activation_generation<>v_generation
       or v_existing.query_fingerprint<>v_query_fingerprint
       or v_existing.query_cohort_fingerprint<>v_cohort_fingerprint
       or v_existing.actual_mode<>v_actual_mode
       or v_existing.proposed_mode<>v_proposed_mode
       or v_existing.actual_score<>v_actual_score
       or v_existing.proposed_score<>v_proposed_score then
      raise exception 'PROJECT_L_LAYER302_COUNTERFACTUAL_REPLAY_MISMATCH';
    end if;

    return jsonb_build_object(
      'status','already_recorded',
      'recorded',false,
      'counterfactualId',v_existing.id,
      'generation',v_existing.activation_generation,
      'actualScore',v_existing.actual_score,
      'proposedScore',v_existing.proposed_score,
      'advantage',v_existing.advantage,
      'proposedWon',v_existing.proposed_won
    );
  end if;

  return jsonb_build_object(
    'status','recorded',
    'recorded',true,
    'counterfactualId',v_id,
    'generation',v_generation,
    'actualScore',v_actual_score,
    'proposedScore',v_proposed_score,
    'advantage',v_advantage,
    'proposedWon',v_advantage>0,
    'materialLoss',v_advantage<=-0.10
  );
end;
$$;

revoke all on function public.project_l_record_adaptive_shadow_counterfactual_v1(
  uuid,text,text,text,text,text,text,text,text,jsonb,jsonb,boolean,timestamptz
) from public, anon, authenticated;

grant execute on function public.project_l_record_adaptive_shadow_counterfactual_v1(
  uuid,text,text,text,text,text,text,text,text,jsonb,jsonb,boolean,timestamptz
) to service_role;

-- Extend Layer 301 stack health with Layer 302 counterfactual machinery.
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

  v_adaptation_table boolean := to_regclass('public.project_l_retrieval_adaptation_events') is not null;
  v_lease_table boolean := to_regclass('public.project_l_retrieval_strategy_leases') is not null;
  v_outcome_table boolean := to_regclass('public.project_l_retrieval_served_outcomes') is not null;
  v_query_binding_table boolean := to_regclass('public.project_l_retrieval_outcome_query_bindings') is not null;
  v_cohort_binding_table boolean := to_regclass('public.project_l_retrieval_outcome_cohort_bindings') is not null;
  v_shadow_table boolean := to_regclass('public.project_l_adaptive_memory_shadow_observations') is not null;
  v_counterfactual_table boolean := to_regclass('public.project_l_adaptive_memory_shadow_counterfactuals') is not null;

  v_adaptation_rls boolean := false;
  v_lease_rls boolean := false;
  v_outcome_rls boolean := false;
  v_query_binding_rls boolean := false;
  v_cohort_binding_rls boolean := false;
  v_shadow_rls boolean := false;
  v_counterfactual_rls boolean := false;

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

  v_stack_ready :=
    v_293 and v_294 and v_295
    and v_296_record and v_296_feed
    and v_297 and v_298
    and v_299_record and v_299_feed
    and v_301_record and v_301_cert
    and v_302_score and v_302_record and v_302_cert
    and v_adaptation_table and coalesce(v_adaptation_rls,false)
    and v_lease_table and coalesce(v_lease_rls,false)
    and v_outcome_table and coalesce(v_outcome_rls,false)
    and v_query_binding_table and coalesce(v_query_binding_rls,false)
    and v_cohort_binding_table and coalesce(v_cohort_binding_rls,false)
    and v_shadow_table and coalesce(v_shadow_rls,false)
    and v_counterfactual_table and coalesce(v_counterfactual_rls,false);

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
      ('adaptation_table_rls',v_adaptation_table and coalesce(v_adaptation_rls,false)),
      ('lease_table_rls',v_lease_table and coalesce(v_lease_rls,false)),
      ('outcome_table_rls',v_outcome_table and coalesce(v_outcome_rls,false)),
      ('query_binding_table_rls',v_query_binding_table and coalesce(v_query_binding_rls,false)),
      ('cohort_binding_table_rls',v_cohort_binding_table and coalesce(v_cohort_binding_rls,false)),
      ('shadow_observation_table_rls',v_shadow_table and coalesce(v_shadow_rls,false)),
      ('shadow_counterfactual_table_rls',v_counterfactual_table and coalesce(v_counterfactual_rls,false))
  ) as checks(name,ready)
  where not ready;

  return jsonb_build_object(
    'version','layer302-v1',
    'requiredLayerFloor',302,
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
    'requiredLayerFloor',302,
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
    pg_catalog.hashtextextended('project_l_adaptive_memory_activation',302)
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
    required_layer_floor=302,
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

comment on table public.project_l_adaptive_memory_shadow_counterfactuals is
  'Layer 302 append-only, content-free current-generation comparisons between served retrieval quality and unused shadow-proposed retrieval quality.';

comment on function public.project_l_retrieval_proxy_score_v1(jsonb) is
  'Layer 302 deterministic retrieval quality proxy, intentionally matching Layer 296 scoring so served and counterfactual paths are directly comparable.';

comment on function public.project_l_adaptive_counterfactual_certification_v1(
  bigint,timestamptz
) is
  'Layer 302 quality certificate requiring repeated, broad, low-downside counterfactual advantage before adaptive retrieval can activate.';

comment on function public.project_l_record_adaptive_shadow_counterfactual_v1(
  uuid,text,text,text,text,text,text,text,text,jsonb,jsonb,boolean,timestamptz
) is
  'Layer 302 generation-bound counterfactual recorder. Only automatic healthy SHADOW_ONLY mode-changing comparisons count.';

comment on function public.project_l_adaptive_memory_activation_status_v1() is
  'Layers 300-302 activation status: ACTIVE influence requires stack health, Layer 301 burn-in, and Layer 302 counterfactual quality certification.';

comment on function public.project_l_set_adaptive_memory_activation_v1(
  text,text,bigint,timestamptz
) is
  'Layers 300-302 activation control: ACTIVE requires healthy stack plus current-generation burn-in and counterfactual quality certificates.';
