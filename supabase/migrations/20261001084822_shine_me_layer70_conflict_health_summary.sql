create or replace function public.shine_me_owner_state_conflict_health_service_v1(
  p_owner_id text
)
returns table (
  health_status text,
  detections_24h integer,
  resolutions_24h integer,
  unresolved_conflicts integer,
  oldest_unresolved_minutes integer,
  last_conflict_at timestamptz,
  recurring boolean,
  persistent boolean
)
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_detections integer := 0;
  v_resolutions integer := 0;
  v_unresolved integer := 0;
  v_oldest_minutes integer := 0;
  v_last_conflict timestamptz;
  v_recurring boolean := false;
  v_persistent boolean := false;
  v_health text := 'stable';
begin
  if p_owner_id is null or btrim(p_owner_id) = '' then
    raise exception 'OWNER_ID_REQUIRED';
  end if;

  select count(*)::integer, max(e.created_at)
    into v_detections, v_last_conflict
  from private.shine_me_owner_state_conflict_events e
  where e.owner_id = p_owner_id
    and e.event_type = 'detected'
    and e.created_at >= now() - interval '24 hours';

  select count(*)::integer
    into v_resolutions
  from private.shine_me_owner_state_conflict_events e
  where e.owner_id = p_owner_id
    and e.event_type = 'resolved'
    and e.created_at >= now() - interval '24 hours';

  with unresolved as (
    select d.created_at
    from private.shine_me_owner_state_conflict_events d
    where d.owner_id = p_owner_id
      and d.event_type = 'detected'
      and not exists (
        select 1
        from private.shine_me_owner_state_conflict_events r
        where r.owner_id = d.owner_id
          and r.conflict_id = d.conflict_id
          and r.event_type = 'resolved'
      )
  )
  select
    count(*)::integer,
    coalesce(
      floor(extract(epoch from (now() - min(created_at))) / 60)::integer,
      0
    )
  into v_unresolved, v_oldest_minutes
  from unresolved;

  v_recurring := v_detections >= 3;
  v_persistent := (
    v_detections >= 6
    or v_unresolved >= 2
    or v_oldest_minutes >= 30
  );

  v_health := case
    when v_persistent then 'persistent'
    when v_recurring then 'recurring'
    when v_detections > 0 or v_unresolved > 0 then 'isolated'
    else 'stable'
  end;

  return query
  select
    v_health,
    v_detections,
    v_resolutions,
    v_unresolved,
    v_oldest_minutes,
    v_last_conflict,
    v_recurring,
    v_persistent;
end;
$$;

revoke all on function public.shine_me_owner_state_conflict_health_service_v1(text)
  from public, anon, authenticated;
grant execute on function public.shine_me_owner_state_conflict_health_service_v1(text)
  to service_role;

comment on function public.shine_me_owner_state_conflict_health_service_v1(text) is
  'Shine Me Layer 70 service-only bounded conflict health summary. Uses revision-event metadata only; stable/isolated/recurring/persistent classification never reads owner-state content.';
