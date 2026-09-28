create index if not exists companion_pending_jobs_delayed_ready_idx
  on public.companion_foundation_pending_jobs(user_id, updated_at desc)
  where status='completed' and synthesis_status='ready';
