create table if not exists private.shine_me_owner_state_conflict_events (
  id bigint generated always as identity primary key,
  conflict_id uuid not null,
  owner_id text not null,
  event_type text not null check (event_type in ('detected','resolved')),
  local_revision bigint not null check (local_revision >= 0),
  remote_revision bigint not null check (remote_revision >= 1),
  resolution text check (resolution in ('account_copy','device_copy')),
  resolved_revision bigint check (resolved_revision >= 1),
  created_at timestamptz not null default now(),
  unique (conflict_id, event_type),
  check (
    (event_type = 'detected' and resolution is null and resolved_revision is null)
    or
    (event_type = 'resolved' and resolution is not null and resolved_revision is not null)
  )
);

comment on table private.shine_me_owner_state_conflict_events is
  'Shine Me Layer 69 privacy-safe owner-state conflict ledger. Stores only opaque conflict identity, revisions, timestamps and explicit resolution choice; never owner-state content.';

alter table private.shine_me_owner_state_conflict_events enable row level security;

revoke all on private.shine_me_owner_state_conflict_events from public, anon, authenticated;
grant usage on schema private to service_role;
grant select, insert on private.shine_me_owner_state_conflict_events to service_role;

create index if not exists shine_me_owner_state_conflict_owner_time_idx
  on private.shine_me_owner_state_conflict_events(owner_id, created_at desc);

create index if not exists shine_me_owner_state_conflict_id_time_idx
  on private.shine_me_owner_state_conflict_events(conflict_id, created_at);

create or replace function public.shine_me_owner_state_conflict_detect_service_v1(
  p_owner_id text,
  p_local_revision bigint
)
returns table (
  conflict_id uuid,
  remote_revision bigint,
  recent_conflicts_24h integer,
  recurring boolean
)
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_remote_revision bigint;
  v_conflict_id uuid;
  v_recent integer;
begin
  if p_owner_id is null or btrim(p_owner_id) = '' then
    raise exception 'OWNER_ID_REQUIRED';
  end if;
  if p_local_revision is null or p_local_revision < 0 then
    raise exception 'LOCAL_REVISION_INVALID';
  end if;

  select s.revision
    into v_remote_revision
  from public.shine_me_owner_state s
  where s.owner_id = p_owner_id;

  if v_remote_revision is null or v_remote_revision = p_local_revision then
    raise exception 'NO_ACTIVE_REVISION_CONFLICT';
  end if;

  select d.conflict_id
    into v_conflict_id
  from private.shine_me_owner_state_conflict_events d
  where d.owner_id = p_owner_id
    and d.event_type = 'detected'
    and d.local_revision = p_local_revision
    and d.remote_revision = v_remote_revision
    and d.created_at >= now() - interval '10 minutes'
    and not exists (
      select 1
      from private.shine_me_owner_state_conflict_events r
      where r.conflict_id = d.conflict_id
        and r.event_type = 'resolved'
    )
  order by d.created_at desc
  limit 1;

  if v_conflict_id is null then
    v_conflict_id := gen_random_uuid();
    insert into private.shine_me_owner_state_conflict_events(
      conflict_id,
      owner_id,
      event_type,
      local_revision,
      remote_revision
    )
    values (
      v_conflict_id,
      p_owner_id,
      'detected',
      p_local_revision,
      v_remote_revision
    );
  end if;

  select count(*)::integer
    into v_recent
  from private.shine_me_owner_state_conflict_events e
  where e.owner_id = p_owner_id
    and e.event_type = 'detected'
    and e.created_at >= now() - interval '24 hours';

  return query
  select
    v_conflict_id,
    v_remote_revision,
    v_recent,
    v_recent >= 3;
end;
$$;

revoke all on function public.shine_me_owner_state_conflict_detect_service_v1(text,bigint)
  from public, anon, authenticated;
grant execute on function public.shine_me_owner_state_conflict_detect_service_v1(text,bigint)
  to service_role;

comment on function public.shine_me_owner_state_conflict_detect_service_v1(text,bigint) is
  'Layer 69 service-only conflict detector. Records revision metadata only, deduplicates the same unresolved conflict briefly and returns bounded 24-hour recurrence state.';

create or replace function public.shine_me_owner_state_conflict_resolve_service_v1(
  p_owner_id text,
  p_conflict_id uuid,
  p_resolution text,
  p_resolved_revision bigint
)
returns table (
  status text,
  resolution text,
  resolved_revision bigint
)
language plpgsql
security invoker
set search_path = ''
as $$
declare
  v_detected record;
  v_existing record;
begin
  if p_owner_id is null or btrim(p_owner_id) = '' then
    raise exception 'OWNER_ID_REQUIRED';
  end if;
  if p_conflict_id is null then
    raise exception 'CONFLICT_ID_REQUIRED';
  end if;
  if p_resolution not in ('account_copy','device_copy') then
    raise exception 'RESOLUTION_INVALID';
  end if;
  if p_resolved_revision is null or p_resolved_revision < 1 then
    raise exception 'RESOLVED_REVISION_INVALID';
  end if;

  select
    d.local_revision,
    d.remote_revision
  into v_detected
  from private.shine_me_owner_state_conflict_events d
  where d.owner_id = p_owner_id
    and d.conflict_id = p_conflict_id
    and d.event_type = 'detected'
  limit 1;

  if not found then
    raise exception 'CONFLICT_NOT_FOUND';
  end if;

  select r.resolution, r.resolved_revision
    into v_existing
  from private.shine_me_owner_state_conflict_events r
  where r.owner_id = p_owner_id
    and r.conflict_id = p_conflict_id
    and r.event_type = 'resolved'
  limit 1;

  if found then
    if v_existing.resolution = p_resolution
       and v_existing.resolved_revision = p_resolved_revision then
      return query
      select 'already_resolved'::text, v_existing.resolution, v_existing.resolved_revision;
      return;
    end if;
    raise exception 'CONFLICT_ALREADY_RESOLVED';
  end if;

  if p_resolution = 'account_copy'
     and p_resolved_revision <> v_detected.remote_revision then
    raise exception 'ACCOUNT_RESOLUTION_REVISION_MISMATCH';
  end if;

  if p_resolution = 'device_copy'
     and p_resolved_revision <= v_detected.remote_revision then
    raise exception 'DEVICE_RESOLUTION_REVISION_MISMATCH';
  end if;

  insert into private.shine_me_owner_state_conflict_events(
    conflict_id,
    owner_id,
    event_type,
    local_revision,
    remote_revision,
    resolution,
    resolved_revision
  )
  values (
    p_conflict_id,
    p_owner_id,
    'resolved',
    v_detected.local_revision,
    v_detected.remote_revision,
    p_resolution,
    p_resolved_revision
  );

  return query
  select 'resolved'::text, p_resolution, p_resolved_revision;
end;
$$;

revoke all on function public.shine_me_owner_state_conflict_resolve_service_v1(text,uuid,text,bigint)
  from public, anon, authenticated;
grant execute on function public.shine_me_owner_state_conflict_resolve_service_v1(text,uuid,text,bigint)
  to service_role;

comment on function public.shine_me_owner_state_conflict_resolve_service_v1(text,uuid,text,bigint) is
  'Layer 69 service-only explicit conflict-resolution receipt. Records account/device choice and revision only; never state content.';
