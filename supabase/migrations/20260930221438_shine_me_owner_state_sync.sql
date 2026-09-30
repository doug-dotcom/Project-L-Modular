-- Applied to Shine-L as migration 20260930221438.
-- Owner-bound Shine Me dashboard/journal state. This is not Project L memory.
create table if not exists public.shine_me_owner_state (
  owner_id text primary key,
  state jsonb not null default '{}'::jsonb,
  revision bigint not null default 1 check (revision >= 1),
  updated_at timestamptz not null default now()
);

comment on table public.shine_me_owner_state is
  'Owner-bound Shine Me dashboard/journal state. Separate from Project L memory; browser clients never access this table directly.';

create index if not exists shine_me_owner_state_updated_idx
  on public.shine_me_owner_state(updated_at desc);

alter table public.shine_me_owner_state enable row level security;
revoke all on public.shine_me_owner_state from public, anon, authenticated;
grant select, insert, update on public.shine_me_owner_state to service_role;
