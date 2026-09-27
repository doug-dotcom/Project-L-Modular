-- Applied to Shine-L as migration 20260927071458.
-- Corrections are proposed review items, never memory records.
create table if not exists public.shine_me_correction_reviews (
  id uuid primary key default gen_random_uuid(),
  owner_id text not null,
  question text not null check (char_length(question) between 1 and 2000),
  source text not null check (char_length(source) between 1 and 160),
  provenance text not null check (provenance in ('user_statement','model_statement','unknown')),
  original_reply text not null check (char_length(original_reply) between 1 and 1500),
  issue_kind text not null check (issue_kind in ('wrong','incomplete')),
  proposed_correction text not null check (char_length(proposed_correction) between 1 and 2000),
  status text not null default 'pending_review' check (status in ('pending_review','reviewed','rejected')),
  created_at timestamptz not null default now()
);
create index if not exists shine_me_correction_reviews_owner_created_idx
  on public.shine_me_correction_reviews(owner_id, created_at desc);
alter table public.shine_me_correction_reviews enable row level security;
revoke all on public.shine_me_correction_reviews from public, anon, authenticated;
grant select, insert on public.shine_me_correction_reviews to service_role;
