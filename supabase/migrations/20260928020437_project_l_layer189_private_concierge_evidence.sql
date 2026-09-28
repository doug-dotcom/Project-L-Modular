create table if not exists private.companion_concierge_synthesis_evidence (
  request_id uuid primary key
    references public.companion_foundation_pending_jobs(job_id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  result_packet jsonb not null
    check (jsonb_typeof(result_packet)='object'),
  result_sha256 text not null
    check (result_sha256 ~ '^[a-f0-9]{64}$'),
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp()
);

revoke all on private.companion_concierge_synthesis_evidence
  from public, anon, authenticated;
grant select, insert, update, delete
  on private.companion_concierge_synthesis_evidence
  to service_role;

alter table public.companion_foundation_pending_jobs
  drop constraint if exists companion_pending_jobs_final_result_object,
  drop column if exists final_result_packet;
