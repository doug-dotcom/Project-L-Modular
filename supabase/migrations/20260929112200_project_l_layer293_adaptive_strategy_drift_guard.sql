-- Project L Layer 293 — Adaptive Strategy Drift Guard
-- Prevents learned retrieval preferences from drifting on stale, bursty,
-- oscillating, or otherwise weak served evidence.
--
-- Invariants carried forward from Layer 292:
--   * explicit caller retrieval choices are never overridden here;
--   * trust / authority / promotion / factual-assertion / corroboration rules
--     are outside this layer and remain unchanged;
--   * this guard only decides whether a learned mode transition is stable
--     enough to be recorded.

create table if not exists public.project_l_retrieval_adaptation_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  intent text not null,
  base_mode text not null check (base_mode in ('lexical','semantic','hybrid')),
  learned_mode text not null check (learned_mode in ('lexical','semantic','hybrid')),
  evidence_window_start timestamptz,
  evidence_window_end timestamptz,
  supporting_sample_count integer not null check (supporting_sample_count >= 0),
  distinct_evidence_days integer not null check (distinct_evidence_days >= 0),
  evidence_span_hours numeric,
  burst_share numeric,
  base_average_score numeric,
  learned_average_score numeric,
  advantage numeric,
  guard_snapshot jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists project_l_retrieval_adaptation_events_user_intent_created_idx
  on public.project_l_retrieval_adaptation_events(user_id, intent, created_at desc);

alter table public.project_l_retrieval_adaptation_events enable row level security;

revoke all on table public.project_l_retrieval_adaptation_events
  from public, anon, authenticated;

grant select, insert on table public.project_l_retrieval_adaptation_events
  to service_role;

create or replace function public.project_l_adaptive_strategy_drift_guard_v1(
  p_user uuid,
  p_intent text,
  p_base_mode text,
  p_candidate_mode text,
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
  v_base text := lower(btrim(coalesce(p_base_mode,'')));
  v_candidate text := lower(btrim(coalesce(p_candidate_mode,'')));

  v_candidate_count integer := 0;
  v_candidate_days integer := 0;
  v_candidate_start timestamptz;
  v_candidate_end timestamptz;
  v_candidate_last_24h integer := 0;
  v_candidate_avg numeric;
  v_base_avg numeric;
  v_span_hours numeric := 0;
  v_burst_share numeric := 0;
  v_advantage numeric;

  v_last_event public.project_l_retrieval_adaptation_events%rowtype;
  v_have_last boolean := false;
  v_duplicate boolean := false;
  v_cooldown boolean := false;
  v_oscillation boolean := false;
  v_cooldown_remaining_hours numeric := 0;

  v_reasons jsonb := '[]'::jsonb;
  v_allowed boolean := false;
  v_event_id uuid;
  v_guard jsonb;
begin
  if p_user is null then
    raise exception 'PROJECT_L_LAYER293_USER_REQUIRED';
  end if;

  if v_intent = '' then
    raise exception 'PROJECT_L_LAYER293_INTENT_REQUIRED';
  end if;

  if v_base not in ('lexical','semantic','hybrid')
     or v_candidate not in ('lexical','semantic','hybrid') then
    raise exception 'PROJECT_L_LAYER293_INVALID_MODE';
  end if;

  if p_outcomes is null or jsonb_typeof(p_outcomes) <> 'array' then
    raise exception 'PROJECT_L_LAYER293_OUTCOMES_ARRAY_REQUIRED';
  end if;

  -- Serialize transitions for one owner + intent so concurrent calls cannot
  -- create duplicate preference-switch events.
  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(p_user::text || '|' || v_intent, 293)
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
      and served_at is not null
      and served_at <= p_now
      and score between 0 and 1
      and mode in ('lexical','semantic','hybrid')
  )
  select
    count(*) filter (where mode = v_candidate),
    count(distinct ((served_at at time zone 'UTC')::date))
      filter (where mode = v_candidate),
    min(served_at) filter (where mode = v_candidate),
    max(served_at) filter (where mode = v_candidate),
    count(*) filter (
      where mode = v_candidate
        and served_at > p_now - interval '24 hours'
    ),
    avg(score) filter (where mode = v_candidate),
    avg(score) filter (where mode = v_base)
  into
    v_candidate_count,
    v_candidate_days,
    v_candidate_start,
    v_candidate_end,
    v_candidate_last_24h,
    v_candidate_avg,
    v_base_avg
  from usable;

  if v_candidate_count > 0 and v_candidate_start is not null and v_candidate_end is not null then
    v_span_hours :=
      round((extract(epoch from (v_candidate_end - v_candidate_start)) / 3600.0)::numeric, 4);
    v_burst_share :=
      round((v_candidate_last_24h::numeric / v_candidate_count::numeric), 6);
  end if;

  if v_candidate_avg is not null and v_base_avg is not null then
    v_advantage := round((v_candidate_avg - v_base_avg)::numeric, 6);
  end if;

  select *
  into v_last_event
  from public.project_l_retrieval_adaptation_events
  where user_id = p_user
    and intent = v_intent
  order by created_at desc, id desc
  limit 1;

  v_have_last := found;

  if v_have_last then
    v_duplicate :=
      v_last_event.base_mode = v_base
      and v_last_event.learned_mode = v_candidate;

    if not v_duplicate and v_last_event.created_at > p_now - interval '72 hours' then
      v_cooldown := true;
      v_cooldown_remaining_hours :=
        round(
          greatest(
            0,
            extract(epoch from ((v_last_event.created_at + interval '72 hours') - p_now)) / 3600.0
          )::numeric,
          4
        );
    end if;

    -- A direct reversal inside seven days is treated as oscillation even once
    -- the 72h switch cooldown has expired.
    if not v_duplicate
       and v_last_event.base_mode = v_candidate
       and v_last_event.learned_mode = v_base
       and v_last_event.created_at > p_now - interval '7 days' then
      v_oscillation := true;
    end if;
  end if;

  if v_candidate = v_base then
    v_reasons := v_reasons || jsonb_build_array('no_mode_change');
  end if;

  if v_candidate_count < 5 then
    v_reasons := v_reasons || jsonb_build_array('insufficient_served_support');
  end if;

  if v_candidate_days < 3 then
    v_reasons := v_reasons || jsonb_build_array('insufficient_distinct_days');
  end if;

  if v_span_hours < 48 then
    v_reasons := v_reasons || jsonb_build_array('insufficient_evidence_span');
  end if;

  if v_candidate_end is null or v_candidate_end < p_now - interval '14 days' then
    v_reasons := v_reasons || jsonb_build_array('stale_evidence');
  end if;

  if v_candidate_count > 0 and v_burst_share > 0.60 then
    v_reasons := v_reasons || jsonb_build_array('last_24h_burst_dominance');
  end if;

  if v_cooldown then
    v_reasons := v_reasons || jsonb_build_array('mode_switch_cooldown');
  end if;

  if v_oscillation then
    v_reasons := v_reasons || jsonb_build_array('mode_oscillation');
  end if;

  -- Layer 292 remains the adaptation threshold authority. Requiring the same
  -- minimum advantage here is defence-in-depth and cannot weaken that rule.
  if v_advantage is null or v_advantage < 0.08 then
    v_reasons := v_reasons || jsonb_build_array('insufficient_advantage');
  end if;

  -- Repeated requests for an already-recorded identical preference are
  -- idempotent: do not create another event.
  if v_duplicate then
    v_allowed := true;
  else
    v_allowed := jsonb_array_length(v_reasons) = 0;
  end if;

  v_guard := jsonb_build_object(
    'version','layer293-v1',
    'requirements',jsonb_build_object(
      'minimumSupportingServedOutcomes',5,
      'minimumDistinctDays',3,
      'minimumSpanHours',48,
      'maximumEvidenceAgeDays',14,
      'maximumLast24hBurstShare',0.60,
      'modeSwitchCooldownHours',72,
      'oscillationWindowDays',7,
      'minimumAdvantage',0.08
    ),
    'observed',jsonb_build_object(
      'supportingServedOutcomes',v_candidate_count,
      'distinctDays',v_candidate_days,
      'evidenceWindowStart',v_candidate_start,
      'evidenceWindowEnd',v_candidate_end,
      'evidenceSpanHours',v_span_hours,
      'last24hBurstShare',v_burst_share,
      'baseAverageScore',v_base_avg,
      'candidateAverageScore',v_candidate_avg,
      'advantage',v_advantage,
      'cooldownActive',v_cooldown,
      'cooldownRemainingHours',v_cooldown_remaining_hours,
      'oscillationDetected',v_oscillation
    ),
    'reasons',v_reasons
  );

  if v_allowed and not v_duplicate and v_candidate <> v_base then
    insert into public.project_l_retrieval_adaptation_events(
      user_id,
      intent,
      base_mode,
      learned_mode,
      evidence_window_start,
      evidence_window_end,
      supporting_sample_count,
      distinct_evidence_days,
      evidence_span_hours,
      burst_share,
      base_average_score,
      learned_average_score,
      advantage,
      guard_snapshot,
      created_at
    )
    values (
      p_user,
      v_intent,
      v_base,
      v_candidate,
      v_candidate_start,
      v_candidate_end,
      v_candidate_count,
      v_candidate_days,
      v_span_hours,
      v_burst_share,
      v_base_avg,
      v_candidate_avg,
      v_advantage,
      v_guard,
      p_now
    )
    returning id into v_event_id;
  end if;

  return jsonb_build_object(
    'status',case
      when v_duplicate then 'already_preferred'
      when v_allowed then 'allowed'
      else 'blocked'
    end,
    'allowed',v_allowed,
    'intent',v_intent,
    'baseMode',v_base,
    'candidateMode',v_candidate,
    'duplicateSuppressed',v_duplicate,
    'eventRecorded',v_event_id is not null,
    'eventId',v_event_id,
    'guard',v_guard
  );
end;
$$;

revoke all on function public.project_l_adaptive_strategy_drift_guard_v1(
  uuid,text,text,text,jsonb,timestamptz
) from public, anon, authenticated;

grant execute on function public.project_l_adaptive_strategy_drift_guard_v1(
  uuid,text,text,text,jsonb,timestamptz
) to service_role;

comment on function public.project_l_adaptive_strategy_drift_guard_v1(
  uuid,text,text,text,jsonb,timestamptz
) is
  'Layer 293: fail-closed stability guard for learned Project L retrieval-mode transitions. Uses served evidence only and records idempotent adaptation events.';
