create index if not exists companion_completion_outbox_conversation_ready_idx
  on public.companion_concierge_completion_outbox(
    user_id, source_conversation_id, created_at
  )
  where summary_state='ready-to-surface';
