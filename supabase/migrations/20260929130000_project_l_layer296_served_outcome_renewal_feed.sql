-- Project L Layer 296 — Served Outcome Capture & Renewal Feed
--
-- Converts real retrieval telemetry into bounded served-outcome evidence.
--
-- Critical learning boundary:
--   * runtime telemetry may renew/revoke an already-earned Layer 293 strategy;
--   * deterministic self-telemetry is NOT eligible to promote a new strategy;
--   * explicit overrides, runtime fallbacks, and default-path outcomes do not
--     count as lease-renewal evidence unless they were genuinely served by an
--     active learned lease;
--   * raw memory content is never written to this ledger.

create table if not exists public.project_l_retrieval_served_outcomes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  request_id text not null,
  intent text not null,
  mode text not null check (mode in ('lexical','semantic','hybrid')),
  served_at timestamptz not null,
  returned_count integer not null check (returned_count >= 0),
  safe_assertion_count integer not null check (safe_assertion_count >= 0),
  corroborated_count integer not null check (corroborated_count >= 0),
  needs_corroboration_count integer not null check (needs_corroboration_count >= 0),
  unique_domain_count integer not null check (unique_domain_count >= 0),
  unique_subject_count integer not null check (unique_subject_count >= 0),
  diversity_fallback_used boolean not null default false,
  retrieval_fallback_used boolean not null default false,
  cache_hit boolean,
  runtime_strategy_source text not null,
  runtime_strategy_reason text,
  lease_applied boolean not null default false,
  explicit_mode_used boolean not null default false,
  quality_score numeric not null check (quality_score between 0 and 1),
  score_model text not null,
  renewal_eligible boolean not null default false,
  adaptation_eligible boolean not null default false,
  evidence_snapshot jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(user_id, request_id)
);

create index if not exists project_l_retrieval_served_outcomes_feed_idx
  on public.project_l_retrieval_served_outcomes(
    user_id,
    intent,
    served_at desc
  );

create index if not exists project_l_retrieval_served_outcomes_renewal_idx
  on public.project_l_retrieval_served_outcomes(
    user_id,
    intent,
    renewal_eligible,
    served_at desc
  );

alter table public.project_l_retrieval_served_outcomes enable row level security;

revoke all on table public.project_l_retrieval_served_outcomes
  from public, anon, authenticated;

-- Append-only operational evidence. No UPDATE/DELETE grants.
grant select, insert on table public.project_l_retrieval_served_outcomes
  to service_role;

create or replace function public.project_l_record_served_outcome_v1(
  p_user uuid,
  p_request_id text,
  p_intent text,
  p_mode text,
  p_payload jsonb,
  p_served_at timestamptz default now()
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
  v_mode text := lower(btrim(coalesce(p_mode,'')));

  v_returned integer := 0;
  v_safe integer := 0;
  v_corr integer := 0;
  v_needs integer := 0;
  v_domains integer := 0;
  v_subjects integer := 0;

  v_diversity_fallback boolean := false;
  v_retrieval_fallback boolean := false;
  v_cache_hit boolean;
  v_source text := 'runtime_default';
  v_reason text;
  v_lease_applied boolean := false;
  v_explicit boolean := false;

  v_safe_ratio numeric := 0;
  v_corr_ratio numeric := 0;
  v_needs_ratio numeric := 0;
  v_diversity_ratio numeric := 0;
  v_score numeric := 0.10;

  v_renewal_eligible boolean := false;
  v_id uuid;
  v_existing public.project_l_retrieval_served_outcomes%rowtype;
  v_snapshot jsonb;
begin
  if p_user is null then
    raise exception 'PROJECT_L_LAYER296_USER_REQUIRED';
  end if;

  if v_request_id = '' then
    raise exception 'PROJECT_L_LAYER296_REQUEST_ID_REQUIRED';
  end if;

  if v_intent = '' then
    raise exception 'PROJECT_L_LAYER296_INTENT_REQUIRED';
  end if;

  if v_mode not in ('lexical','semantic','hybrid') then
    raise exception 'PROJECT_L_LAYER296_INVALID_MODE';
  end if;

  if p_payload is null or jsonb_typeof(p_payload) <> 'object' then
    raise exception 'PROJECT_L_LAYER296_PAYLOAD_OBJECT_REQUIRED';
  end if;

  if octet_length(p_payload::text) > 8000 then
    raise exception 'PROJECT_L_LAYER296_PAYLOAD_TOO_LARGE';
  end if;

  if coalesce(p_payload->>'returned_count','') ~ '^[0-9]+$' then
    v_returned := least((p_payload->>'returned_count')::integer,1000);
  end if;
  if coalesce(p_payload->>'safe_assertion_count','') ~ '^[0-9]+$' then
    v_safe := least((p_payload->>'safe_assertion_count')::integer,1000);
  end if;
  if coalesce(p_payload->>'corroborated_count','') ~ '^[0-9]+$' then
    v_corr := least((p_payload->>'corroborated_count')::integer,1000);
  end if;
  if coalesce(p_payload->>'needs_corroboration_count','') ~ '^[0-9]+$' then
    v_needs := least((p_payload->>'needs_corroboration_count')::integer,1000);
  end if;
  if coalesce(p_payload->>'unique_domain_count','') ~ '^[0-9]+$' then
    v_domains := least((p_payload->>'unique_domain_count')::integer,1000);
  end if;
  if coalesce(p_payload->>'unique_subject_count','') ~ '^[0-9]+$' then
    v_subjects := least((p_payload->>'unique_subject_count')::integer,1000);
  end if;

  v_diversity_fallback :=
    lower(coalesce(p_payload->>'diversity_fallback_used','false'))
      in ('true','1','yes');
  v_retrieval_fallback :=
    lower(coalesce(p_payload->>'retrieval_fallback_used','false'))
      in ('true','1','yes');
  v_lease_applied :=
    lower(coalesce(p_payload->>'lease_applied','false'))
      in ('true','1','yes');
  v_explicit :=
    lower(coalesce(p_payload->>'explicit_mode_used','false'))
      in ('true','1','yes');

  if p_payload ? 'cache_hit'
     and lower(coalesce(p_payload->>'cache_hit','')) in ('true','false') then
    v_cache_hit := (p_payload->>'cache_hit')::boolean;
  end if;

  v_source := left(
    coalesce(nullif(btrim(p_payload->>'runtime_strategy_source'),''),'runtime_default'),
    80
  );
  v_reason := nullif(left(btrim(coalesce(p_payload->>'runtime_strategy_reason','')),240),'');

  if v_returned > 0 then
    v_safe_ratio :=
      least(v_safe,v_returned)::numeric / v_returned::numeric;
    v_corr_ratio :=
      least(v_corr,v_returned)::numeric / v_returned::numeric;
    v_needs_ratio :=
      least(v_needs,v_returned)::numeric / v_returned::numeric;
    v_diversity_ratio :=
      least(
        1::numeric,
        v_subjects::numeric /
          greatest(1,least(v_returned,4))::numeric
      );

    -- Bounded deterministic proxy. It deliberately measures observable
    -- retrieval quality, not user satisfaction or semantic truth.
    v_score :=
      0.25
      + (0.35 * v_safe_ratio)
      + (0.20 * v_corr_ratio)
      + (0.10 * v_diversity_ratio)
      + case when not v_diversity_fallback then 0.10 else 0 end
      - (0.20 * v_needs_ratio)
      - case when v_retrieval_fallback then 0.05 else 0 end;

    v_score := round(least(0.95,greatest(0.05,v_score)),6);
  else
    v_score := 0.10;
  end if;

  -- Only evidence actually served because an active learned lease selected the
  -- mode may renew that lease. Explicit overrides/defaults/fallbacks cannot.
  v_renewal_eligible :=
    v_lease_applied
    and v_source = 'active_lease'
    and not v_explicit
    and not v_retrieval_fallback
    and v_returned > 0;

  v_snapshot := jsonb_build_object(
    'version','layer296-v1',
    'scoreModel','deterministic_retrieval_proxy_v1',
    'raw',jsonb_build_object(
      'returnedCount',v_returned,
      'safeAssertionCount',v_safe,
      'corroboratedCount',v_corr,
      'needsCorroborationCount',v_needs,
      'uniqueDomainCount',v_domains,
      'uniqueSubjectCount',v_subjects,
      'diversityFallbackUsed',v_diversity_fallback,
      'retrievalFallbackUsed',v_retrieval_fallback,
      'cacheHit',v_cache_hit,
      'runtimeStrategySource',v_source,
      'runtimeStrategyReason',v_reason,
      'leaseApplied',v_lease_applied,
      'explicitModeUsed',v_explicit
    ),
    'derived',jsonb_build_object(
      'safeRatio',round(v_safe_ratio,6),
      'corroboratedRatio',round(v_corr_ratio,6),
      'needsCorroborationRatio',round(v_needs_ratio,6),
      'diversityRatio',round(v_diversity_ratio,6),
      'qualityScore',v_score,
      'renewalEligible',v_renewal_eligible,
      'adaptationEligible',false
    )
  );

  insert into public.project_l_retrieval_served_outcomes(
    user_id,
    request_id,
    intent,
    mode,
    served_at,
    returned_count,
    safe_assertion_count,
    corroborated_count,
    needs_corroboration_count,
    unique_domain_count,
    unique_subject_count,
    diversity_fallback_used,
    retrieval_fallback_used,
    cache_hit,
    runtime_strategy_source,
    runtime_strategy_reason,
    lease_applied,
    explicit_mode_used,
    quality_score,
    score_model,
    renewal_eligible,
    adaptation_eligible,
    evidence_snapshot
  )
  values (
    p_user,
    v_request_id,
    v_intent,
    v_mode,
    p_served_at,
    v_returned,
    v_safe,
    v_corr,
    v_needs,
    v_domains,
    v_subjects,
    v_diversity_fallback,
    v_retrieval_fallback,
    v_cache_hit,
    v_source,
    v_reason,
    v_lease_applied,
    v_explicit,
    v_score,
    'deterministic_retrieval_proxy_v1',
    v_renewal_eligible,
    false,
    v_snapshot
  )
  on conflict (user_id,request_id) do nothing
  returning id into v_id;

  if v_id is null then
    select *
    into v_existing
    from public.project_l_retrieval_served_outcomes
    where user_id=p_user and request_id=v_request_id;

    return jsonb_build_object(
      'status','already_recorded',
      'outcomeId',v_existing.id,
      'mode',v_existing.mode,
      'qualityScore',v_existing.quality_score,
      'renewalEligible',v_existing.renewal_eligible,
      'adaptationEligible',v_existing.adaptation_eligible,
      'duplicateSuppressed',true
    );
  end if;

  return jsonb_build_object(
    'status','recorded',
    'outcomeId',v_id,
    'mode',v_mode,
    'qualityScore',v_score,
    'scoreModel','deterministic_retrieval_proxy_v1',
    'renewalEligible',v_renewal_eligible,
    'adaptationEligible',false,
    'duplicateSuppressed',false
  );
end;
$$;

revoke all on function public.project_l_record_served_outcome_v1(
  uuid,text,text,text,jsonb,timestamptz
) from public, anon, authenticated;

grant execute on function public.project_l_record_served_outcome_v1(
  uuid,text,text,text,jsonb,timestamptz
) to service_role;

create or replace function public.project_l_served_outcome_feed_v1(
  p_user uuid,
  p_intent text,
  p_purpose text default 'renewal',
  p_since timestamptz default null,
  p_limit integer default 64
)
returns jsonb
language plpgsql
stable
security invoker
set search_path = ''
set statement_timeout = '5s'
as $$
declare
  v_intent text := left(lower(btrim(coalesce(p_intent,''))),80);
  v_purpose text := lower(btrim(coalesce(p_purpose,'renewal')));
  v_limit integer := least(greatest(coalesce(p_limit,64),1),128);
  v_lease_start timestamptz;
  v_since timestamptz;
  v_result jsonb;
begin
  if p_user is null then
    raise exception 'PROJECT_L_LAYER296_USER_REQUIRED';
  end if;

  if v_intent = '' then
    raise exception 'PROJECT_L_LAYER296_INTENT_REQUIRED';
  end if;

  if v_purpose not in ('renewal','adaptation') then
    raise exception 'PROJECT_L_LAYER296_INVALID_FEED_PURPOSE';
  end if;

  if v_purpose = 'renewal' then
    select lease_started_at
    into v_lease_start
    from public.project_l_retrieval_strategy_leases
    where user_id=p_user and intent=v_intent
    order by updated_at desc,created_at desc
    limit 1;
  end if;

  v_since := coalesce(
    p_since,
    case
      when v_purpose='renewal' then v_lease_start
      else now()-interval '14 days'
    end,
    now()-interval '14 days'
  );

  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'evidence_id',x.id,
        'mode',x.mode,
        'score',x.quality_score,
        'served',true,
        'served_at',x.served_at,
        'score_model',x.score_model
      )
      order by x.served_at asc,x.id asc
    ),
    '[]'::jsonb
  )
  into v_result
  from (
    select *
    from public.project_l_retrieval_served_outcomes
    where user_id=p_user
      and intent=v_intent
      and served_at > v_since
      and (
        (v_purpose='renewal' and renewal_eligible=true)
        or
        (v_purpose='adaptation' and adaptation_eligible=true)
      )
    order by served_at desc,id desc
    limit v_limit
  ) x;

  return v_result;
end;
$$;

revoke all on function public.project_l_served_outcome_feed_v1(
  uuid,text,text,timestamptz,integer
) from public, anon, authenticated;

grant execute on function public.project_l_served_outcome_feed_v1(
  uuid,text,text,timestamptz,integer
) to service_role;

create or replace function public.project_l_auto_renewal_feed_v1(
  p_user uuid,
  p_intent text,
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
  v_outcomes jsonb;
  v_evaluation jsonb;
begin
  v_outcomes := public.project_l_served_outcome_feed_v1(
    p_user,
    p_intent,
    'renewal',
    null,
    64
  );

  v_evaluation := public.project_l_strategy_lease_status_v1(
    p_user,
    p_intent,
    v_outcomes,
    p_now
  );

  return jsonb_build_object(
    'status','evaluated',
    'outcomesCount',jsonb_array_length(v_outcomes),
    'leaseEvaluation',v_evaluation
  );
end;
$$;

revoke all on function public.project_l_auto_renewal_feed_v1(
  uuid,text,timestamptz
) from public, anon, authenticated;

grant execute on function public.project_l_auto_renewal_feed_v1(
  uuid,text,timestamptz
) to service_role;

comment on table public.project_l_retrieval_served_outcomes is
  'Layer 296 append-only, content-free served retrieval telemetry used for lease renewal evidence; proxy rows are never adaptation-eligible.';

comment on function public.project_l_record_served_outcome_v1(
  uuid,text,text,text,jsonb,timestamptz
) is
  'Layer 296: idempotently record bounded content-free served retrieval telemetry and deterministic renewal-only quality evidence.';

comment on function public.project_l_served_outcome_feed_v1(
  uuid,text,text,timestamptz,integer
) is
  'Layer 296: bounded served-outcome feed for renewal or stronger future adaptation evidence.';

comment on function public.project_l_auto_renewal_feed_v1(
  uuid,text,timestamptz
) is
  'Layer 296: feed eligible real served outcomes into Layer 294 lease evaluation.';
