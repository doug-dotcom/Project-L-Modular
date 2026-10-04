-- Project L Layer 294 — Strategy Lease & Renewal
--
-- Learned retrieval preferences are leases, not permanent rewrites.
-- Layer 293 decides whether a learned mode transition is stable enough to enter.
-- Layer 294 requires that learned mode to continue earning its place from fresh,
-- post-transition served outcomes.
--
-- This layer never governs explicit caller mode choices and never weakens
-- authority, promotion, factual-assertion, corroboration, or trust rules.

create table if not exists public.project_l_retrieval_strategy_leases (
  adaptation_event_id uuid primary key
    references public.project_l_retrieval_adaptation_events(id)
    on delete restrict,
  user_id uuid not null,
  intent text not null,
  base_mode text not null check (base_mode in ('lexical','semantic','hybrid')),
  learned_mode text not null check (learned_mode in ('lexical','semantic','hybrid')),
  state text not null default 'active'
    check (state in ('active','expired','revoked')),
  lease_started_at timestamptz not null,
  lease_expires_at timestamptz not null,
  renewal_count integer not null default 0 check (renewal_count >= 0),
  last_evidence_at timestamptz,
  last_evaluated_at timestamptz,
  last_decision text,
  updated_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  check (lease_expires_at > lease_started_at)
);

create index if not exists project_l_retrieval_strategy_leases_user_intent_idx
  on public.project_l_retrieval_strategy_leases(user_id, intent, updated_at desc);

alter table public.project_l_retrieval_strategy_leases enable row level security;

revoke all on table public.project_l_retrieval_strategy_leases
  from public, anon, authenticated;

grant select, insert, update on table public.project_l_retrieval_strategy_leases
  to service_role;

create table if not exists public.project_l_retrieval_strategy_lease_events (
  id uuid primary key default gen_random_uuid(),
  adaptation_event_id uuid not null
    references public.project_l_retrieval_adaptation_events(id)
    on delete restrict,
  user_id uuid not null,
  intent text not null,
  action text not null
    check (action in ('created','renewed','expired','revoked')),
  prior_lease_expires_at timestamptz,
  lease_expires_at timestamptz,
  evidence_window_start timestamptz,
  evidence_window_end timestamptz,
  supporting_sample_count integer not null default 0
    check (supporting_sample_count >= 0),
  distinct_evidence_days integer not null default 0
    check (distinct_evidence_days >= 0),
  evidence_span_hours numeric,
  learned_average_score numeric,
  quality_floor numeric,
  evidence_snapshot jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists project_l_retrieval_strategy_lease_events_lookup_idx
  on public.project_l_retrieval_strategy_lease_events(
    adaptation_event_id,
    created_at desc
  );

alter table public.project_l_retrieval_strategy_lease_events enable row level security;

revoke all on table public.project_l_retrieval_strategy_lease_events
  from public, anon, authenticated;

grant select, insert on table public.project_l_retrieval_strategy_lease_events
  to service_role;

create or replace function public.project_l_strategy_lease_status_v1(
  p_user uuid,
  p_intent text,
  p_outcomes jsonb,
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
  v_intent text := lower(btrim(coalesce(p_intent,'')));
  v_adaptation public.project_l_retrieval_adaptation_events%rowtype;
  v_lease public.project_l_retrieval_strategy_leases%rowtype;
  v_have_adaptation boolean := false;
  v_have_lease boolean := false;

  v_count integer := 0;
  v_days integer := 0;
  v_window_start timestamptz;
  v_window_end timestamptz;
  v_span_hours numeric := 0;
  v_avg numeric;

  v_original_base numeric;
  v_original_learned numeric;
  v_quality_floor numeric := 0.55;

  v_sufficient boolean := false;
  v_fresh boolean := false;
  v_action text := 'active';
  v_effective_mode text;
  v_event_action text;
  v_prior_expiry timestamptz;
  v_new_expiry timestamptz;
  v_snapshot jsonb;
begin
  if p_user is null then
    raise exception 'PROJECT_L_LAYER294_USER_REQUIRED';
  end if;

  if v_intent = '' then
    raise exception 'PROJECT_L_LAYER294_INTENT_REQUIRED';
  end if;

  if p_outcomes is null or jsonb_typeof(p_outcomes) <> 'array' then
    raise exception 'PROJECT_L_LAYER294_OUTCOMES_ARRAY_REQUIRED';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(p_user::text || '|' || v_intent, 294)
  );

  select *
  into v_adaptation
  from public.project_l_retrieval_adaptation_events
  where user_id = p_user
    and intent = v_intent
  order by created_at desc, id desc
  limit 1;

  v_have_adaptation := found;

  if not v_have_adaptation then
    return jsonb_build_object(
      'status','no_learned_strategy',
      'effectiveMode',null,
      'leaseActive',false,
      'reason','no_layer293_adaptation_event'
    );
  end if;

  select *
  into v_lease
  from public.project_l_retrieval_strategy_leases
  where adaptation_event_id = v_adaptation.id
  for update;

  v_have_lease := found;

  if not v_have_lease then
    insert into public.project_l_retrieval_strategy_leases(
      adaptation_event_id,
      user_id,
      intent,
      base_mode,
      learned_mode,
      state,
      lease_started_at,
      lease_expires_at,
      renewal_count,
      last_decision,
      last_evaluated_at,
      updated_at
    )
    values (
      v_adaptation.id,
      p_user,
      v_intent,
      v_adaptation.base_mode,
      v_adaptation.learned_mode,
      'active',
      v_adaptation.created_at,
      v_adaptation.created_at + interval '7 days',
      0,
      'created',
      p_now,
      p_now
    )
    returning * into v_lease;

    insert into public.project_l_retrieval_strategy_lease_events(
      adaptation_event_id,
      user_id,
      intent,
      action,
      lease_expires_at,
      evidence_snapshot,
      created_at
    )
    values (
      v_adaptation.id,
      p_user,
      v_intent,
      'created',
      v_lease.lease_expires_at,
      jsonb_build_object(
        'layer','294',
        'leaseDays',7,
        'source','layer293_adaptation_event'
      ),
      p_now
    );
  end if;

  -- Terminal lease states do not auto-revive. A future learned transition must
  -- come through Layer 293 as a new adaptation event.
  if v_lease.state in ('expired','revoked') then
    return jsonb_build_object(
      'status',v_lease.state,
      'effectiveMode',v_lease.base_mode,
      'learnedMode',v_lease.learned_mode,
      'baseMode',v_lease.base_mode,
      'leaseActive',false,
      'leaseStartedAt',v_lease.lease_started_at,
      'leaseExpiresAt',v_lease.lease_expires_at,
      'renewalCount',v_lease.renewal_count,
      'reason','terminal_lease_requires_new_layer293_transition'
    );
  end if;

  v_original_base := v_adaptation.base_average_score;
  v_original_learned := v_adaptation.learned_average_score;

  -- Renewal quality floor:
  --   * absolute minimum 0.55;
  --   * still at least 0.03 above the original base-mode mean where known;
  --   * no more than 0.08 deterioration from the original learned-mode mean.
  v_quality_floor := greatest(
    0.55::numeric,
    coalesce(v_original_base + 0.03, 0.55::numeric),
    coalesce(v_original_learned - 0.08, 0.55::numeric)
  );

  with parsed as (
    select
      lower(btrim(coalesce(x->>'mode',''))) as mode,
      lower(coalesce(x->>'served','false')) in ('true','1','yes') as served,
      case
        when coalesce(x->>'score','') ~ '^-?([0-9]+([.][0-9]+)?|[.][0-9]+)$'
          then (x->>'score')::numeric
        else null
      end as score,
      case
        when coalesce(x->>'served_at','') <> ''
          then (x->>'served_at')::timestamptz
        else null
      end as served_at
    from jsonb_array_elements(p_outcomes) x
  ),
  usable as (
    select *
    from parsed
    where served
      and mode = v_lease.learned_mode
      and served_at is not null
      and served_at > v_lease.lease_started_at
      and served_at <= p_now
      and score between 0 and 1
  )
  select
    count(*),
    count(distinct ((served_at at time zone 'UTC')::date)),
    min(served_at),
    max(served_at),
    avg(score)
  into
    v_count,
    v_days,
    v_window_start,
    v_window_end,
    v_avg
  from usable;

  if v_count > 0 and v_window_start is not null and v_window_end is not null then
    v_span_hours :=
      round((extract(epoch from (v_window_end - v_window_start)) / 3600.0)::numeric, 4);
  end if;

  v_fresh :=
    v_window_end is not null
    and v_window_end >= p_now - interval '72 hours';

  v_sufficient :=
    v_count >= 5
    and v_days >= 3
    and v_span_hours >= 48
    and v_fresh;

  v_snapshot := jsonb_build_object(
    'version','layer294-v1',
    'requirements',jsonb_build_object(
      'leaseDays',7,
      'minimumSupportingServedOutcomes',5,
      'minimumDistinctDays',3,
      'minimumEvidenceSpanHours',48,
      'freshEvidenceWithinHours',72,
      'absoluteQualityFloor',0.55,
      'minimumMarginAboveOriginalBase',0.03,
      'maximumDropFromOriginalLearned',0.08
    ),
    'observed',jsonb_build_object(
      'supportingServedOutcomes',v_count,
      'distinctDays',v_days,
      'evidenceWindowStart',v_window_start,
      'evidenceWindowEnd',v_window_end,
      'evidenceSpanHours',v_span_hours,
      'fresh',v_fresh,
      'sufficient',v_sufficient,
      'learnedAverageScore',v_avg,
      'originalBaseAverageScore',v_original_base,
      'originalLearnedAverageScore',v_original_learned,
      'qualityFloor',v_quality_floor
    )
  );

  v_prior_expiry := v_lease.lease_expires_at;

  if v_sufficient and v_avg < v_quality_floor then
    -- Evidence is strong enough to judge, and the learned mode has materially
    -- degraded. Revoke early rather than waiting for the calendar lease.
    v_action := 'revoked';
    v_effective_mode := v_lease.base_mode;
    v_event_action := 'revoked';

    update public.project_l_retrieval_strategy_leases
    set
      state = 'revoked',
      last_evidence_at = v_window_end,
      last_evaluated_at = p_now,
      last_decision = 'revoked_quality_decay',
      updated_at = p_now
    where adaptation_event_id = v_lease.adaptation_event_id
    returning * into v_lease;

  elsif v_sufficient and v_avg >= v_quality_floor then
    -- Fresh, distributed post-switch evidence still supports the learned mode.
    -- Renew from now; old evidence cannot immediately renew the next cycle.
    v_action := 'renewed';
    v_effective_mode := v_lease.learned_mode;
    v_event_action := 'renewed';
    v_new_expiry := p_now + interval '7 days';

    update public.project_l_retrieval_strategy_leases
    set
      lease_started_at = p_now,
      lease_expires_at = v_new_expiry,
      renewal_count = renewal_count + 1,
      last_evidence_at = v_window_end,
      last_evaluated_at = p_now,
      last_decision = 'renewed_fresh_served_evidence',
      updated_at = p_now
    where adaptation_event_id = v_lease.adaptation_event_id
    returning * into v_lease;

  elsif p_now >= v_lease.lease_expires_at then
    -- No sufficient fresh evidence arrived before expiry. Fail back to the
    -- pre-learning base mode; do not invent confidence from absence of data.
    v_action := 'expired';
    v_effective_mode := v_lease.base_mode;
    v_event_action := 'expired';

    update public.project_l_retrieval_strategy_leases
    set
      state = 'expired',
      last_evidence_at = v_window_end,
      last_evaluated_at = p_now,
      last_decision = 'expired_insufficient_fresh_evidence',
      updated_at = p_now
    where adaptation_event_id = v_lease.adaptation_event_id
    returning * into v_lease;

  else
    -- Lease remains active while waiting for enough distributed evidence.
    v_action := 'active';
    v_effective_mode := v_lease.learned_mode;

    update public.project_l_retrieval_strategy_leases
    set
      last_evidence_at = greatest(last_evidence_at, v_window_end),
      last_evaluated_at = p_now,
      last_decision = 'active_waiting_for_renewal_evidence',
      updated_at = p_now
    where adaptation_event_id = v_lease.adaptation_event_id
    returning * into v_lease;
  end if;

  if v_event_action is not null then
    insert into public.project_l_retrieval_strategy_lease_events(
      adaptation_event_id,
      user_id,
      intent,
      action,
      prior_lease_expires_at,
      lease_expires_at,
      evidence_window_start,
      evidence_window_end,
      supporting_sample_count,
      distinct_evidence_days,
      evidence_span_hours,
      learned_average_score,
      quality_floor,
      evidence_snapshot,
      created_at
    )
    values (
      v_lease.adaptation_event_id,
      p_user,
      v_intent,
      v_event_action,
      v_prior_expiry,
      v_lease.lease_expires_at,
      v_window_start,
      v_window_end,
      v_count,
      v_days,
      v_span_hours,
      v_avg,
      v_quality_floor,
      v_snapshot,
      p_now
    );
  end if;

  return jsonb_build_object(
    'status',v_action,
    'effectiveMode',v_effective_mode,
    'learnedMode',v_lease.learned_mode,
    'baseMode',v_lease.base_mode,
    'leaseActive',v_lease.state = 'active',
    'leaseStartedAt',v_lease.lease_started_at,
    'leaseExpiresAt',v_lease.lease_expires_at,
    'renewalCount',v_lease.renewal_count,
    'evaluation',v_snapshot
  );
end;
$$;

revoke all on function public.project_l_strategy_lease_status_v1(
  uuid,text,jsonb,timestamptz
) from public, anon, authenticated;

grant execute on function public.project_l_strategy_lease_status_v1(
  uuid,text,jsonb,timestamptz
) to service_role;

comment on function public.project_l_strategy_lease_status_v1(
  uuid,text,jsonb,timestamptz
) is
  'Layer 294: time-bounded lease and fresh-evidence renewal for learned Project L retrieval strategies. Explicit caller choices are outside this lifecycle.';
