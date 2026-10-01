create or replace function public.shine_me_owner_state_conflict_health_explain_service_v1(
  p_owner_id text
)
returns table (
  health_status text,
  reason_codes text[],
  recovery_state text,
  detections_24h integer,
  resolutions_24h integer,
  unresolved_conflicts integer,
  oldest_unresolved_minutes integer,
  last_conflict_at timestamptz
)
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_health record;
  v_reasons text[] := array[]::text[];
  v_recovery text := 'clear';
begin
  if p_owner_id is null or btrim(p_owner_id) = '' then
    raise exception 'OWNER_ID_REQUIRED';
  end if;

  select *
    into v_health
  from public.shine_me_owner_state_conflict_health_service_v1(p_owner_id);

  if v_health.health_status in ('recurring','persistent')
     and v_health.detections_24h >= 3 then
    v_reasons := array_append(v_reasons, 'volume');
  end if;

  if v_health.unresolved_conflicts >= 2 then
    v_reasons := array_append(v_reasons, 'unresolved_count');
  end if;

  if v_health.oldest_unresolved_minutes >= 30 then
    v_reasons := array_append(v_reasons, 'unresolved_age');
  end if;

  v_recovery := case
    when v_health.unresolved_conflicts >= 2
      or v_health.oldest_unresolved_minutes >= 30
      then 'stalled'
    when v_health.unresolved_conflicts > 0
      then 'resolving'
    when v_health.detections_24h > 0
      then 'observing'
    else 'clear'
  end;

  return query
  select
    v_health.health_status::text,
    v_reasons,
    v_recovery,
    v_health.detections_24h::integer,
    v_health.resolutions_24h::integer,
    v_health.unresolved_conflicts::integer,
    v_health.oldest_unresolved_minutes::integer,
    v_health.last_conflict_at::timestamptz;
end;
$$;

revoke all on function public.shine_me_owner_state_conflict_health_explain_service_v1(text)
  from public, anon, authenticated;
grant execute on function public.shine_me_owner_state_conflict_health_explain_service_v1(text)
  to service_role;

comment on function public.shine_me_owner_state_conflict_health_explain_service_v1(text) is
  'Shine Me Layer 71 service-only explanation over bounded sync-conflict health. Returns reason codes and recovery state from operational conflict metadata only; never reads owner-state content or resolves a conflict.';
