-- Project L Layer 298 — Evidence Independence Guard
--
-- Prevents repeated/correlated versions of the same query from masquerading
-- as broad renewal evidence.
--
-- Privacy boundary:
--   * stores only a SHA-256 fingerprint of normalized query text;
--   * raw query text is never stored in the evidence ledger;
--   * one query fingerprint contributes at most its earliest and latest
--     eligible served outcomes to lease evaluation.
--
-- Learning boundary:
--   * this layer still cannot create a new learned strategy;
--   * it only hardens Layer 297 lease evaluation against correlated evidence.

create table if not exists public.project_l_retrieval_outcome_query_bindings (
  outcome_id uuid primary key
    references public.project_l_retrieval_served_outcomes(id)
    on delete restrict,
  user_id uuid not null,
  query_fingerprint text not null
    check (query_fingerprint ~ '^[0-9a-f]{64}$'),
  fingerprint_version text not null default 'sha256-norm-v1',
  created_at timestamptz not null default now()
);

create index if not exists project_l_retrieval_outcome_query_bindings_lookup_idx
  on public.project_l_retrieval_outcome_query_bindings(
    user_id,
    query_fingerprint,
    created_at desc
  );

alter table public.project_l_retrieval_outcome_query_bindings
  enable row level security;

revoke all on table public.project_l_retrieval_outcome_query_bindings
  from public, anon, authenticated;

grant select, insert on table public.project_l_retrieval_outcome_query_bindings
  to service_role;

create or replace function public.project_l_record_served_outcome_bound_v1(
  p_user uuid,
  p_request_id text,
  p_intent text,
  p_mode text,
  p_query_fingerprint text,
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
  v_fingerprint text := lower(btrim(coalesce(p_query_fingerprint,'')));
  v_record jsonb;
  v_outcome_id uuid;
  v_binding public.project_l_retrieval_outcome_query_bindings%rowtype;
begin
  if v_fingerprint !~ '^[0-9a-f]{64}$' then
    raise exception 'PROJECT_L_LAYER298_INVALID_QUERY_FINGERPRINT';
  end if;

  v_record := public.project_l_record_served_outcome_v1(
    p_user,
    p_request_id,
    p_intent,
    p_mode,
    p_payload,
    p_served_at
  );

  begin
    v_outcome_id := (v_record->>'outcomeId')::uuid;
  exception
    when others then
      raise exception 'PROJECT_L_LAYER298_OUTCOME_ID_REQUIRED';
  end;

  insert into public.project_l_retrieval_outcome_query_bindings(
    outcome_id,
    user_id,
    query_fingerprint,
    fingerprint_version
  )
  values (
    v_outcome_id,
    p_user,
    v_fingerprint,
    'sha256-norm-v1'
  )
  on conflict (outcome_id) do nothing;

  select *
  into v_binding
  from public.project_l_retrieval_outcome_query_bindings
  where outcome_id=v_outcome_id;

  if not found then
    raise exception 'PROJECT_L_LAYER298_QUERY_BINDING_MISSING';
  end if;

  if v_binding.user_id <> p_user then
    raise exception 'PROJECT_L_LAYER298_QUERY_BINDING_OWNER_MISMATCH';
  end if;

  if v_binding.query_fingerprint <> v_fingerprint then
    raise exception 'PROJECT_L_LAYER298_FINGERPRINT_MISMATCH';
  end if;

  return v_record || jsonb_build_object(
    'queryFingerprintBound',true,
    'fingerprintVersion','sha256-norm-v1'
  );
end;
$$;

revoke all on function public.project_l_record_served_outcome_bound_v1(
  uuid,text,text,text,text,jsonb,timestamptz
) from public, anon, authenticated;

grant execute on function public.project_l_record_served_outcome_bound_v1(
  uuid,text,text,text,text,jsonb,timestamptz
) to service_role;

create or replace function public.project_l_independent_served_outcome_feed_v1(
  p_user uuid,
  p_intent text,
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
  v_limit integer := least(greatest(coalesce(p_limit,64),1),128);
  v_lease_start timestamptz;
  v_since timestamptz;
  v_result jsonb;
begin
  if p_user is null then
    raise exception 'PROJECT_L_LAYER298_USER_REQUIRED';
  end if;

  if v_intent = '' then
    raise exception 'PROJECT_L_LAYER298_INTENT_REQUIRED';
  end if;

  select lease_started_at
  into v_lease_start
  from public.project_l_retrieval_strategy_leases
  where user_id=p_user and intent=v_intent
  order by updated_at desc,created_at desc
  limit 1;

  v_since := coalesce(
    p_since,
    v_lease_start,
    now()-interval '14 days'
  );

  with eligible as (
    select
      o.*,
      b.query_fingerprint,
      row_number() over (
        partition by b.query_fingerprint
        order by o.served_at asc,o.id asc
      ) as rn_oldest,
      row_number() over (
        partition by b.query_fingerprint
        order by o.served_at desc,o.id desc
      ) as rn_newest
    from public.project_l_retrieval_served_outcomes o
    join public.project_l_retrieval_outcome_query_bindings b
      on b.outcome_id=o.id
     and b.user_id=o.user_id
    where o.user_id=p_user
      and o.intent=v_intent
      and o.renewal_eligible=true
      and o.served_at > v_since
  ),
  independent as (
    select *
    from eligible
    where rn_oldest=1 or rn_newest=1
    order by served_at desc,id desc
    limit v_limit
  )
  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'evidence_id',id,
        'mode',mode,
        'score',quality_score,
        'served',true,
        'served_at',served_at,
        'score_model',score_model,
        'query_fingerprint',query_fingerprint
      )
      order by served_at asc,id asc
    ),
    '[]'::jsonb
  )
  into v_result
  from independent;

  return v_result;
end;
$$;

revoke all on function public.project_l_independent_served_outcome_feed_v1(
  uuid,text,timestamptz,integer
) from public, anon, authenticated;

grant execute on function public.project_l_independent_served_outcome_feed_v1(
  uuid,text,timestamptz,integer
) to service_role;

-- Harden the Layer 297 evaluator in place so the runtime API remains stable.
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
  v_query_fingerprints integer := 0;
  v_window_start timestamptz;
  v_window_end timestamptz;
  v_span_hours numeric := 0;
  v_avg numeric;
  v_fresh boolean := false;
  v_strong boolean := false;
  v_independent boolean := false;

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
    pg_catalog.hashtextextended(p_user::text || '|' || v_intent, 298)
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

  v_outcomes := public.project_l_independent_served_outcome_feed_v1(
    p_user,
    v_intent,
    v_lease.lease_started_at,
    64
  );

  with parsed as (
    select
      x->>'query_fingerprint' as query_fingerprint,
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
      and coalesce(query_fingerprint,'') ~ '^[0-9a-f]{64}$'
  )
  select
    count(*),
    count(distinct ((served_at at time zone 'UTC')::date)),
    count(distinct query_fingerprint),
    min(served_at),
    max(served_at),
    avg(score)
  into
    v_count,
    v_days,
    v_query_fingerprints,
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

  v_independent := v_query_fingerprints >= 3;

  v_strong :=
    v_count >= 5
    and v_days >= 3
    and v_span_hours >= 48
    and v_fresh
    and v_independent;

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
      'independentEvidence',v_independent,
      'distinctQueryFingerprints',v_query_fingerprints,
      'qualityDecay',true,
      'qualityFloor',v_quality_floor,
      'averageScore',v_avg,
      'independentOutcomesCount',v_count,
      'leaseEvaluation',v_evaluation
    );
  end if;

  if not v_renewal_window_open then
    return jsonb_build_object(
      'status','monitoring',
      'requestId',v_request_id,
      'mutationPerformed',false,
      'renewalWindowOpen',false,
      'hoursUntilExpiry',v_hours_until_expiry,
      'strongEvidence',v_strong,
      'independentEvidence',v_independent,
      'distinctQueryFingerprints',v_query_fingerprints,
      'qualityDecay',false,
      'qualityFloor',v_quality_floor,
      'averageScore',v_avg,
      'independentOutcomesCount',v_count,
      'leaseState',v_lease.state,
      'leaseExpiresAt',v_lease.lease_expires_at,
      'renewalCount',v_lease.renewal_count,
      'reason',case
        when not v_independent then 'insufficient_query_independence'
        else 'positive_renewal_blocked_until_final_24_hours'
      end
    );
  end if;

  -- At/after expiry, always delegate the clock transition to Layer 294.
  -- Before expiry, correlated evidence cannot trigger a positive mutation.
  if not v_independent and p_now < v_lease.lease_expires_at then
    return jsonb_build_object(
      'status','monitoring',
      'requestId',v_request_id,
      'mutationPerformed',false,
      'renewalWindowOpen',true,
      'hoursUntilExpiry',v_hours_until_expiry,
      'strongEvidence',false,
      'independentEvidence',false,
      'distinctQueryFingerprints',v_query_fingerprints,
      'qualityDecay',false,
      'independentOutcomesCount',v_count,
      'leaseState',v_lease.state,
      'leaseExpiresAt',v_lease.lease_expires_at,
      'renewalCount',v_lease.renewal_count,
      'reason','positive_renewal_requires_three_query_fingerprints'
    );
  end if;

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
    'independentEvidence',v_independent,
    'distinctQueryFingerprints',v_query_fingerprints,
    'qualityDecay',false,
    'qualityFloor',v_quality_floor,
    'averageScore',v_avg,
    'independentOutcomesCount',v_count,
    'leaseEvaluation',v_evaluation,
    'leaseDecision',v_status
  );
end;
$$;

comment on table public.project_l_retrieval_outcome_query_bindings is
  'Layer 298 privacy-safe binding of served outcomes to normalized-query SHA-256 fingerprints; no raw query text is stored.';

comment on function public.project_l_record_served_outcome_bound_v1(
  uuid,text,text,text,text,jsonb,timestamptz
) is
  'Layer 298: idempotently bind a served outcome to one privacy-safe normalized-query fingerprint and reject fingerprint replay mismatches.';

comment on function public.project_l_independent_served_outcome_feed_v1(
  uuid,text,timestamptz,integer
) is
  'Layer 298: renewal feed capped to earliest/latest evidence per query fingerprint so repeated queries cannot dominate lease evidence.';

comment on function public.project_l_governed_lease_evaluation_v1(
  uuid,text,text,timestamptz
) is
  'Layers 297-298: blocks positive renewal ratcheting and requires at least three independent normalized-query fingerprints for strong lease evidence.';
