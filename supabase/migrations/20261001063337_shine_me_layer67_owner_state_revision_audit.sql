create table if not exists public.shine_me_owner_state_events (
  id bigint generated always as identity primary key,
  owner_id text not null,
  event_type text not null check (event_type in ('insert','update')),
  prior_revision bigint,
  revision bigint not null check (revision >= 1),
  state_sha256 text not null check (state_sha256 ~ '^[a-f0-9]{64}$'),
  recorded_at timestamptz not null default now(),
  unique (owner_id, revision)
);

comment on table public.shine_me_owner_state_events is
  'Privacy-safe Shine Me owner-state revision ledger. Stores revision metadata and SHA-256 only; never duplicates journal/dashboard state content.';

alter table public.shine_me_owner_state_events enable row level security;

revoke all on public.shine_me_owner_state_events from public, anon, authenticated;
grant select, insert on public.shine_me_owner_state_events to service_role;

create index if not exists shine_me_owner_state_events_owner_time_idx
  on public.shine_me_owner_state_events(owner_id, recorded_at desc);

create or replace function private.shine_me_owner_state_audit_v1()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'UPDATE'
     and old.state is not distinct from new.state
     and old.revision is not distinct from new.revision then
    return new;
  end if;

  insert into public.shine_me_owner_state_events(
    owner_id,
    event_type,
    prior_revision,
    revision,
    state_sha256
  )
  values (
    new.owner_id,
    case when tg_op = 'INSERT' then 'insert' else 'update' end,
    case when tg_op = 'INSERT' then null else old.revision end,
    new.revision,
    encode(extensions.digest(convert_to(new.state::text, 'UTF8'), 'sha256'), 'hex')
  );

  return new;
end;
$$;

revoke all on function private.shine_me_owner_state_audit_v1() from public, anon, authenticated;
grant execute on function private.shine_me_owner_state_audit_v1() to service_role;

drop trigger if exists shine_me_owner_state_audit_v1 on public.shine_me_owner_state;
create trigger shine_me_owner_state_audit_v1
after insert or update of state, revision
on public.shine_me_owner_state
for each row
execute function private.shine_me_owner_state_audit_v1();

create or replace function private.shine_me_owner_state_apply_v1(
  p_owner_id text,
  p_expected_revision bigint,
  p_state jsonb
)
returns table (
  owner_id text,
  revision bigint,
  updated_at timestamptz
)
language plpgsql
set search_path = ''
as $$
begin
  if p_owner_id is null or btrim(p_owner_id) = '' then
    raise exception 'OWNER_ID_REQUIRED';
  end if;

  if p_state is null then
    raise exception 'STATE_REQUIRED';
  end if;

  if p_expected_revision = 0 then
    return query
    insert into public.shine_me_owner_state(owner_id, state, revision)
    values (p_owner_id, p_state, 1)
    on conflict (owner_id) do nothing
    returning shine_me_owner_state.owner_id,
              shine_me_owner_state.revision,
              shine_me_owner_state.updated_at;

    if found then
      return;
    end if;

    raise exception 'REVISION_CONFLICT';
  end if;

  return query
  update public.shine_me_owner_state s
     set state = p_state,
         revision = s.revision + 1,
         updated_at = now()
   where s.owner_id = p_owner_id
     and s.revision = p_expected_revision
  returning s.owner_id, s.revision, s.updated_at;

  if not found then
    raise exception 'REVISION_CONFLICT';
  end if;
end;
$$;

revoke all on function private.shine_me_owner_state_apply_v1(text,bigint,jsonb)
  from public, anon, authenticated;
grant execute on function private.shine_me_owner_state_apply_v1(text,bigint,jsonb)
  to service_role;

comment on function private.shine_me_owner_state_apply_v1(text,bigint,jsonb) is
  'Shine Me Layer 67 atomic owner-state write with optimistic revision control. expected_revision=0 creates revision 1; updates require an exact current revision.';
