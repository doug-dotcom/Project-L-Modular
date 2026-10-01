create table if not exists private.shine_me_owner_state_conflict_health_transitions (
  transition_id uuid primary key default gen_random_uuid(),
  owner_id text not null,
  from_health_status text,
  to_health_status text not null,
  from_recovery_state text,
  to_recovery_state text not null,
  from_reason_codes text[] not null default array[]::text[],
  to_reason_codes text[] not null default array[]::text[],
  direction text not null,
  previous_state_seconds integer not null default 0,
  episode_started_at timestamptz,
  recovered_in_seconds integer,
  observed_at timestamptz not null default now(),
  constraint shine_me_health_transition_from_health_check
    check (from_health_status is null or from_health_status in ('stable','isolated','recurring','persistent')),
  constraint shine_me_health_transition_to_health_check
    check (to_health_status in ('stable','isolated','recurring','persistent')),
  constraint shine_me_health_transition_from_recovery_check
    check (from_recovery_state is null or from_recovery_state in ('clear','observing','resolving','stalled')),
  constraint shine_me_health_transition_to_recovery_check
    check (to_recovery_state in ('clear','observing','resolving','stalled')),
  constraint shine_me_health_transition_direction_check
    check (direction in ('baseline','improving','worsening','recovered','mixed')),
  constraint shine_me_health_transition_previous_seconds_check
    check (previous_state_seconds >= 0),
  constraint shine_me_health_transition_recovered_seconds_check
    check (recovered_in_seconds is null or recovered_in_seconds >= 0),
  constraint shine_me_health_transition_from_reasons_check
    check (
      cardinality(from_reason_codes) <= 3
      and from_reason_codes <@ array['volume','unresolved_count','unresolved_age']::text[]
    ),
  constraint shine_me_health_transition_to_reasons_check
    check (
      cardinality(to_reason_codes) <= 3
      and to_reason_codes <@ array['volume','unresolved_count','unresolved_age']::text[]
    ),
  constraint shine_me_health_transition_baseline_check
    check (
      (direction = 'baseline' and from_health_status is null and from_recovery_state is null)
      or
      (direction <> 'baseline' and from_health_status is not null and from_recovery_state is not null)
    ),
  constraint shine_me_health_transition_recovered_check
    check (
      (direction = 'recovered' and recovered_in_seconds is not null and to_recovery_state = 'clear')
      or
      (direction <> 'recovered' and recovered_in_seconds is null)
    )
);

alter table private.shine_me_owner_state_conflict_health_transitions
  enable row level security;

revoke all on private.shine_me_owner_state_conflict_health_transitions
  from public, anon, authenticated;
grant select, insert, delete on private.shine_me_owner_state_conflict_health_transitions
  to service_role;

create index if not exists shine_me_conflict_health_transitions_owner_time_idx
  on private.shine_me_owner_state_conflict_health_transitions(owner_id, observed_at desc);

create or replace function public.shine_me_owner_state_conflict_health_transition_service_v1(
  p_owner_id text
)
returns table (
  transition_recorded boolean,
  transition_id uuid,
  direction text,
  health_status text,
  recovery_state text,
  reason_codes text[],
  state_age_seconds integer,
  episode_age_seconds integer,
  recovery_seconds integer,
  history_size integer
)
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_now timestamptz := clock_timestamp();
  v_health record;
  v_previous private.shine_me_owner_state_conflict_health_transitions%rowtype;
  v_has_previous boolean := false;
  v_transition_id uuid;
  v_direction text := 'baseline';
  v_previous_seconds integer := 0;
  v_episode_started timestamptz;
  v_episode_age integer := 0;
  v_recovery_seconds integer;
  v_history_size integer := 0;
  v_prev_health_rank integer := 0;
  v_curr_health_rank integer := 0;
  v_prev_recovery_rank integer := 0;
  v_curr_recovery_rank integer := 0;
  v_health_delta integer := 0;
  v_recovery_delta integer := 0;
begin
  if p_owner_id is null or btrim(p_owner_id) = '' then
    raise exception 'OWNER_ID_REQUIRED';
  end if;

  select *
    into v_health
  from public.shine_me_owner_state_conflict_health_explain_service_v1(p_owner_id);

  select *
    into v_previous
  from private.shine_me_owner_state_conflict_health_transitions t
  where t.owner_id = p_owner_id
  order by t.observed_at desc, t.transition_id desc
  limit 1;

  v_has_previous := found;

  if v_has_previous
     and v_previous.to_health_status = v_health.health_status
     and v_previous.to_recovery_state = v_health.recovery_state
     and v_previous.to_reason_codes = v_health.reason_codes then

    delete from private.shine_me_owner_state_conflict_health_transitions t
    where t.owner_id = p_owner_id
      and t.transition_id in (
        select old.transition_id
        from private.shine_me_owner_state_conflict_health_transitions old
        where old.owner_id = p_owner_id
        order by old.observed_at desc, old.transition_id desc
        offset 32
      );

    select count(*)::integer
      into v_history_size
    from private.shine_me_owner_state_conflict_health_transitions t
    where t.owner_id = p_owner_id;

    v_episode_age := case
      when v_previous.to_recovery_state = 'clear' then 0
      when v_previous.episode_started_at is null then 0
      else greatest(0, floor(extract(epoch from (v_now - v_previous.episode_started_at)))::integer)
    end;

    return query
    select
      false,
      v_previous.transition_id,
      'steady'::text,
      v_health.health_status::text,
      v_health.recovery_state::text,
      v_health.reason_codes::text[],
      greatest(0, floor(extract(epoch from (v_now - v_previous.observed_at)))::integer),
      v_episode_age,
      v_previous.recovered_in_seconds,
      v_history_size;
    return;
  end if;

  if not v_has_previous then
    v_direction := 'baseline';
    v_episode_started := case
      when v_health.recovery_state = 'clear' then null
      else v_now
    end;
  else
    v_previous_seconds := greatest(
      0,
      floor(extract(epoch from (v_now - v_previous.observed_at)))::integer
    );

    v_prev_health_rank := case v_previous.to_health_status
      when 'stable' then 0 when 'isolated' then 1
      when 'recurring' then 2 when 'persistent' then 3 else 0 end;
    v_curr_health_rank := case v_health.health_status
      when 'stable' then 0 when 'isolated' then 1
      when 'recurring' then 2 when 'persistent' then 3 else 0 end;
    v_prev_recovery_rank := case v_previous.to_recovery_state
      when 'clear' then 0 when 'observing' then 1
      when 'resolving' then 2 when 'stalled' then 3 else 0 end;
    v_curr_recovery_rank := case v_health.recovery_state
      when 'clear' then 0 when 'observing' then 1
      when 'resolving' then 2 when 'stalled' then 3 else 0 end;

    v_health_delta := v_curr_health_rank - v_prev_health_rank;
    v_recovery_delta := v_curr_recovery_rank - v_prev_recovery_rank;

    if v_health.recovery_state = 'clear'
       and v_previous.to_recovery_state <> 'clear' then
      v_direction := 'recovered';
    elsif v_health_delta <= 0 and v_recovery_delta <= 0
       and (v_health_delta < 0 or v_recovery_delta < 0) then
      v_direction := 'improving';
    elsif v_health_delta >= 0 and v_recovery_delta >= 0
       and (v_health_delta > 0 or v_recovery_delta > 0) then
      v_direction := 'worsening';
    else
      v_direction := 'mixed';
    end if;

    v_episode_started := case
      when v_previous.to_recovery_state = 'clear'
        and v_health.recovery_state <> 'clear'
        then v_now
      when v_previous.episode_started_at is not null
        then v_previous.episode_started_at
      when v_health.recovery_state <> 'clear'
        then v_previous.observed_at
      else null
    end;

    if v_direction = 'recovered' then
      v_recovery_seconds := greatest(
        0,
        floor(
          extract(epoch from (
            v_now - coalesce(v_previous.episode_started_at, v_previous.observed_at)
          ))
        )::integer
      );
    end if;
  end if;

  insert into private.shine_me_owner_state_conflict_health_transitions (
    owner_id,
    from_health_status,
    to_health_status,
    from_recovery_state,
    to_recovery_state,
    from_reason_codes,
    to_reason_codes,
    direction,
    previous_state_seconds,
    episode_started_at,
    recovered_in_seconds,
    observed_at
  )
  values (
    p_owner_id,
    case when v_has_previous then v_previous.to_health_status else null end,
    v_health.health_status,
    case when v_has_previous then v_previous.to_recovery_state else null end,
    v_health.recovery_state,
    case when v_has_previous then v_previous.to_reason_codes else array[]::text[] end,
    v_health.reason_codes,
    v_direction,
    v_previous_seconds,
    v_episode_started,
    v_recovery_seconds,
    v_now
  )
  returning private.shine_me_owner_state_conflict_health_transitions.transition_id
    into v_transition_id;

  delete from private.shine_me_owner_state_conflict_health_transitions t
  where t.owner_id = p_owner_id
    and t.transition_id in (
      select old.transition_id
      from private.shine_me_owner_state_conflict_health_transitions old
      where old.owner_id = p_owner_id
      order by old.observed_at desc, old.transition_id desc
      offset 32
    );

  select count(*)::integer
    into v_history_size
  from private.shine_me_owner_state_conflict_health_transitions t
  where t.owner_id = p_owner_id;

  v_episode_age := case
    when v_health.recovery_state = 'clear' then 0
    when v_episode_started is null then 0
    else greatest(0, floor(extract(epoch from (v_now - v_episode_started)))::integer)
  end;

  return query
  select
    true,
    v_transition_id,
    v_direction,
    v_health.health_status::text,
    v_health.recovery_state::text,
    v_health.reason_codes::text[],
    0,
    v_episode_age,
    v_recovery_seconds,
    v_history_size;
end;
$$;

revoke all on function public.shine_me_owner_state_conflict_health_transition_service_v1(text)
  from public, anon, authenticated;
grant execute on function public.shine_me_owner_state_conflict_health_transition_service_v1(text)
  to service_role;

comment on function public.shine_me_owner_state_conflict_health_transition_service_v1(text) is
  'Shine Me Layer 72 service-only bounded transition observer. Records only changes in content-free sync health, retains at most 32 receipts per owner, reports recovery timing, and never reads or mutates owner-state content.';
