-- Project L Layer 295 — Runtime Lease Enforcement
--
-- Converts Layers 293/294 governance state into a deterministic retrieval-mode
-- decision that the live l-companion runtime can obey.
--
-- Read-only by design:
--   * explicit caller choice has first priority;
--   * active Layer 294 leases may influence automatic mode selection;
--   * expired/revoked leases fall back to the pre-learning base mode;
--   * runtime readiness can block semantic/hybrid execution;
--   * no learning, renewal, expiry mutation, or scoring happens in recall.

create or replace function public.project_l_runtime_retrieval_decision_v1(
  p_user uuid,
  p_intent text,
  p_explicit_mode text default null,
  p_default_mode text default 'lexical',
  p_semantic_ready boolean default false,
  p_hybrid_ready boolean default false,
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
  v_intent text := lower(btrim(coalesce(p_intent,'')));
  v_explicit text := nullif(lower(btrim(coalesce(p_explicit_mode,''))),'');
  v_default text := lower(btrim(coalesce(p_default_mode,'lexical')));
  v_effective_default text;
  v_desired text;
  v_effective text;
  v_source text := 'default';
  v_reason text := null;
  v_adaptation public.project_l_retrieval_adaptation_events%rowtype;
  v_lease public.project_l_retrieval_strategy_leases%rowtype;
  v_have_adaptation boolean := false;
  v_have_lease boolean := false;
  v_lease_active_by_clock boolean := false;
begin
  if p_user is null then
    raise exception 'PROJECT_L_LAYER295_USER_REQUIRED';
  end if;

  if v_intent = '' then
    raise exception 'PROJECT_L_LAYER295_INTENT_REQUIRED';
  end if;

  if v_default not in ('lexical','semantic','hybrid') then
    v_default := 'lexical';
  end if;

  -- Runtime-safe default. Hybrid is deliberately not assumed available.
  if v_default = 'semantic' and coalesce(p_semantic_ready,false) then
    v_effective_default := 'semantic';
  elsif v_default = 'hybrid' and coalesce(p_hybrid_ready,false) then
    v_effective_default := 'hybrid';
  else
    v_effective_default := 'lexical';
  end if;

  -- Explicit caller intent outranks learned preferences, but an unavailable
  -- executor is never pretended to exist.
  if v_explicit is not null then
    if v_explicit not in ('lexical','semantic','hybrid') then
      return jsonb_build_object(
        'status','invalid_explicit_mode',
        'effectiveMode',v_effective_default,
        'requestedMode',v_explicit,
        'source','explicit_request',
        'reason','unsupported_explicit_mode',
        'leaseApplied',false
      );
    end if;

    if v_explicit = 'lexical' then
      v_effective := 'lexical';
      v_reason := 'explicit_mode_available';
    elsif v_explicit = 'semantic' and coalesce(p_semantic_ready,false) then
      v_effective := 'semantic';
      v_reason := 'explicit_mode_available';
    elsif v_explicit = 'hybrid' and coalesce(p_hybrid_ready,false) then
      v_effective := 'hybrid';
      v_reason := 'explicit_mode_available';
    else
      v_effective := v_effective_default;
      v_reason := 'explicit_mode_runtime_unavailable';
    end if;

    return jsonb_build_object(
      'status',case when v_reason='explicit_mode_available' then 'explicit' else 'explicit_unavailable' end,
      'effectiveMode',v_effective,
      'requestedMode',v_explicit,
      'source','explicit_request',
      'reason',v_reason,
      'leaseApplied',false,
      'semanticReady',coalesce(p_semantic_ready,false),
      'hybridReady',coalesce(p_hybrid_ready,false)
    );
  end if;

  select *
  into v_adaptation
  from public.project_l_retrieval_adaptation_events
  where user_id = p_user
    and intent = v_intent
  order by created_at desc, id desc
  limit 1;

  v_have_adaptation := found;

  if v_have_adaptation then
    select *
    into v_lease
    from public.project_l_retrieval_strategy_leases
    where adaptation_event_id = v_adaptation.id;

    v_have_lease := found;
  end if;

  if not v_have_lease then
    return jsonb_build_object(
      'status','default',
      'effectiveMode',v_effective_default,
      'source','runtime_default',
      'reason',case
        when v_have_adaptation then 'adaptation_has_no_layer294_lease'
        else 'no_learned_strategy'
      end,
      'leaseApplied',false,
      'semanticReady',coalesce(p_semantic_ready,false),
      'hybridReady',coalesce(p_hybrid_ready,false)
    );
  end if;

  v_lease_active_by_clock :=
    v_lease.state = 'active'
    and p_now < v_lease.lease_expires_at;

  if v_lease_active_by_clock then
    v_desired := v_lease.learned_mode;
    v_source := 'active_lease';
    v_reason := 'layer294_active_lease';
  else
    v_desired := v_lease.base_mode;
    v_source := case
      when v_lease.state in ('expired','revoked') then 'terminal_lease_base'
      else 'lease_clock_expired_base'
    end;
    v_reason := case
      when v_lease.state = 'revoked' then 'layer294_revoked'
      when v_lease.state = 'expired' then 'layer294_expired'
      else 'lease_expired_by_clock'
    end;
  end if;

  -- Enforce executor readiness. If a learned mode is not executable, prefer
  -- the original base mode before falling all the way back to runtime default.
  if v_desired = 'lexical' then
    v_effective := 'lexical';
  elsif v_desired = 'semantic' and coalesce(p_semantic_ready,false) then
    v_effective := 'semantic';
  elsif v_desired = 'hybrid' and coalesce(p_hybrid_ready,false) then
    v_effective := 'hybrid';
  elsif v_lease.base_mode = 'lexical' then
    v_effective := 'lexical';
    v_reason := v_reason || '_desired_mode_unavailable_fallback_base';
  elsif v_lease.base_mode = 'semantic' and coalesce(p_semantic_ready,false) then
    v_effective := 'semantic';
    v_reason := v_reason || '_desired_mode_unavailable_fallback_base';
  elsif v_lease.base_mode = 'hybrid' and coalesce(p_hybrid_ready,false) then
    v_effective := 'hybrid';
    v_reason := v_reason || '_desired_mode_unavailable_fallback_base';
  else
    v_effective := v_effective_default;
    v_reason := v_reason || '_desired_and_base_unavailable_fallback_default';
  end if;

  return jsonb_build_object(
    'status','decided',
    'effectiveMode',v_effective,
    'desiredMode',v_desired,
    'source',v_source,
    'reason',v_reason,
    'leaseApplied',v_lease_active_by_clock,
    'leaseState',v_lease.state,
    'leaseStartedAt',v_lease.lease_started_at,
    'leaseExpiresAt',v_lease.lease_expires_at,
    'renewalCount',v_lease.renewal_count,
    'baseMode',v_lease.base_mode,
    'learnedMode',v_lease.learned_mode,
    'adaptationEventId',v_adaptation.id,
    'semanticReady',coalesce(p_semantic_ready,false),
    'hybridReady',coalesce(p_hybrid_ready,false)
  );
end;
$$;

revoke all on function public.project_l_runtime_retrieval_decision_v1(
  uuid,text,text,text,boolean,boolean,timestamptz
) from public, anon, authenticated;

grant execute on function public.project_l_runtime_retrieval_decision_v1(
  uuid,text,text,text,boolean,boolean,timestamptz
) to service_role;

comment on function public.project_l_runtime_retrieval_decision_v1(
  uuid,text,text,text,boolean,boolean,timestamptz
) is
  'Layer 295: read-only runtime retrieval-mode enforcement for explicit caller choice plus Layer 294 strategy leases.';
