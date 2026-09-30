-- Project L Layer 297 — Renewal Ratchet Guard
--
-- Layer 296 supplies real served-outcome evidence. This layer controls WHEN
-- that evidence is allowed to extend a learned strategy lease.
--
-- Invariants:
--   * healthy evidence cannot extend a 7-day lease until the final 24 hours;
--   * sufficiently strong degrading evidence may revoke early;
--   * insufficient evidence cannot manufacture a renewal;
--   * expired leases still fail back through Layer 294;
--   * explicit/default/fallback requests remain excluded by Layer 296;
--   * this layer does not create new learned strategies.

create or replace function public.project_l_governed_lease_evaluation_v1(
  p_user uuid,
  p_intent text,
  p_request_id text,
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
  v_intent text := left(lower(btrim(coalesce(p_intent,''))),80);
  v_request_id text := left(btrim(coalesce(p_request_id,'')),120);

  v_adaptation public.project_l_retrieval_adaptation_events%rowtype;
  v_lease public.project_l_retrieval_strategy_leases%rowtype;
  v_have_adaptation boolean := false;
  v_have_lease boolean := false;

  v_outcomes jsonb := '[]'::jsonb;
  v_count integer := 0;
  v_days integer := 0;
  v_window_start timestamptz;
  v_window_end timestamptz;
  v_span_hours numeric := 0;
  v_avg numeric;
  v_fresh boolean := false;
  v_strong boolean := false;

  v_quality_floor numeric := 0.55;
  v_quality_decay boolean := false;

  v_renewal_window_open boolean := false;
  v_hours_until_expiry numeric := 0;
  v_evaluation jsonb;
  v_status text;
begin
  if p_user is null then
    raise exception 'PROJECT_L_LAYER297_USER_REQUIRED';
  end if;

  if v_intent = '' then
    raise exception 'PROJECT_L_LAYER297_INTENT_REQUIRED';
  end if;

  if v_request_id = '' then
    raise exception 'PROJECT_L_LAYER297_REQUEST_ID_REQUIRED';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(p_user::text || '|' || v_intent, 297)
  );

  select *
  into v_adaptation
  from public.project_l_retrieval_adaptation_events
  where user_id=p_user
    and intent=v_intent
  order by created_at desc,id desc
  limit 1;

  v_have_adaptation := found;

  if not v_have_adaptation then
    return jsonb_build_object(
      'status','no_learned_strategy',
      'requestId',v_request_id,
      'mutationPerformed',false,
      'reason','no_layer293_adaptation_event'
    );
  end if;

  select *
  into v_lease
  from public.project_l_retrieval_strategy_leases
  where adaptation_event_id=v_adaptation.id
  for update;

  v_have_lease := found;

  if not v_have_lease then
    return jsonb_build_object(
      'status','no_lease',
      'requestId',v_request_id,
      'mutationPerformed',false,
      'reason','layer294_lease_not_created'
    );
  end if;

  if v_lease.state in ('expired','revoked') then
    return jsonb_build_object(
      'status',v_lease.state,
      'requestId',v_request_id,
      'mutationPerformed',false,
      'effectiveMode',v_lease.base_mode,
      'leaseState',v_lease.state,
      'leaseExpiresAt',v_lease.lease_expires_at,
      'renewalCount',v_lease.renewal_count,
      'reason','terminal_lease'
    );
  end if;

  v_outcomes := public.project_l_served_outcome_feed_v1(
    p_user,
    v_intent,
    'renewal',
    v_lease.lease_started_at,
    64
  );

  with parsed as (
    select
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
    from jsonb_array_elements(v_outcomes) x
  ),
  usable as (
    select *
    from parsed
    where score between 0 and 1
      and served_at is not null
      and served_at > v_lease.lease_started_at
      and served_at <= p_now
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
      round((extract(epoch from (v_window_end-v_window_start))/3600.0)::numeric,4);
  end if;

  v_fresh :=
    v_window_end is not null
    and v_window_end >= p_now-interval '72 hours';

  v_strong :=
    v_count >= 5
    and v_days >= 3
    and v_span_hours >= 48
    and v_fresh;

  v_quality_floor := greatest(
    0.55::numeric,
    coalesce(v_adaptation.base_average_score+0.03,0.55::numeric),
    coalesce(v_adaptation.learned_average_score-0.08,0.55::numeric)
  );

  v_quality_decay :=
    v_strong
    and v_avg is not null
    and v_avg < v_quality_floor;

  v_renewal_window_open :=
    p_now >= v_lease.lease_expires_at-interval '24 hours';

  v_hours_until_expiry :=
    round(
      (extract(epoch from (v_lease.lease_expires_at-p_now))/3600.0)::numeric,
      4
    );

  -- Negative evidence is allowed to act early. Positive evidence is not.
  if v_quality_decay then
    v_evaluation := public.project_l_strategy_lease_status_v1(
      p_user,
      v_intent,
      v_outcomes,
      p_now
    );

    return jsonb_build_object(
      'status','early_quality_review',
      'requestId',v_request_id,
      'mutationPerformed',true,
      'renewalWindowOpen',v_renewal_window_open,
      'hoursUntilExpiry',v_hours_until_expiry,
      'strongEvidence',v_strong,
      'qualityDecay',true,
      'qualityFloor',v_quality_floor,
      'averageScore',v_avg,
      'outcomesCount',v_count,
      'leaseEvaluation',v_evaluation
    );
  end if;

  -- Before the final 24 hours, healthy evidence may be observed but cannot
  -- ratchet the expiry forward.
  if not v_renewal_window_open then
    return jsonb_build_object(
      'status','monitoring',
      'requestId',v_request_id,
      'mutationPerformed',false,
      'renewalWindowOpen',false,
      'hoursUntilExpiry',v_hours_until_expiry,
      'strongEvidence',v_strong,
      'qualityDecay',false,
      'qualityFloor',v_quality_floor,
      'averageScore',v_avg,
      'outcomesCount',v_count,
      'leaseState',v_lease.state,
      'leaseExpiresAt',v_lease.lease_expires_at,
      'renewalCount',v_lease.renewal_count,
      'reason','positive_renewal_blocked_until_final_24_hours'
    );
  end if;

  -- In the renewal window (or after clock expiry), Layer 294 remains the
  -- authoritative renew / active / expire / revoke transition engine.
  v_evaluation := public.project_l_strategy_lease_status_v1(
    p_user,
    v_intent,
    v_outcomes,
    p_now
  );

  v_status := coalesce(v_evaluation->>'status','unknown');

  return jsonb_build_object(
    'status','renewal_window_evaluation',
    'requestId',v_request_id,
    'mutationPerformed',true,
    'renewalWindowOpen',true,
    'hoursUntilExpiry',v_hours_until_expiry,
    'strongEvidence',v_strong,
    'qualityDecay',false,
    'qualityFloor',v_quality_floor,
    'averageScore',v_avg,
    'outcomesCount',v_count,
    'leaseEvaluation',v_evaluation,
    'leaseDecision',v_status
  );
end;
$$;

revoke all on function public.project_l_governed_lease_evaluation_v1(
  uuid,text,text,timestamptz
) from public, anon, authenticated;

grant execute on function public.project_l_governed_lease_evaluation_v1(
  uuid,text,text,timestamptz
) to service_role;

comment on function public.project_l_governed_lease_evaluation_v1(
  uuid,text,text,timestamptz
) is
  'Layer 297: prevents positive lease-renewal ratcheting before the final 24 hours while preserving early revocation on strong degrading evidence.';
