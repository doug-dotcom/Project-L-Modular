alter table public.companion_foundation_pending_jobs
  add column if not exists request_text text,
  add column if not exists final_result_packet jsonb,
  add column if not exists final_result_sha256 text,
  add column if not exists final_answer text,
  add column if not exists final_answer_sha256 text,
  add column if not exists synthesis_status text not null default 'not-required';

alter table public.companion_foundation_pending_jobs
  drop constraint if exists companion_pending_jobs_request_text_len,
  add constraint companion_pending_jobs_request_text_len
    check (request_text is null or length(request_text) <= 100000),
  drop constraint if exists companion_pending_jobs_final_result_object,
  add constraint companion_pending_jobs_final_result_object
    check (final_result_packet is null or jsonb_typeof(final_result_packet)='object'),
  drop constraint if exists companion_pending_jobs_result_sha256,
  add constraint companion_pending_jobs_result_sha256
    check (
      final_result_sha256 is null
      or final_result_sha256 ~ '^[a-f0-9]{64}$'
    ),
  drop constraint if exists companion_pending_jobs_answer_len,
  add constraint companion_pending_jobs_answer_len
    check (final_answer is null or length(final_answer) <= 50000),
  drop constraint if exists companion_pending_jobs_answer_sha256,
  add constraint companion_pending_jobs_answer_sha256
    check (
      final_answer_sha256 is null
      or final_answer_sha256 ~ '^[a-f0-9]{64}$'
    ),
  drop constraint if exists companion_pending_jobs_synthesis_status,
  add constraint companion_pending_jobs_synthesis_status
    check (synthesis_status in ('not-required','pending','ready','failed'));

create or replace function public.companion_claim_completion_event_v2(p_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public'
as $function$
declare
  e public.companion_concierge_completion_outbox%rowtype;
  j public.companion_foundation_pending_jobs%rowtype;
  token uuid:=gen_random_uuid();
begin
  if p_user_id is null then
    raise exception 'user-required' using errcode='22023';
  end if;

  update public.companion_concierge_completion_outbox
  set summary_state='ready-to-surface',lease_token=null,lease_expires_at=null
  where user_id=p_user_id and summary_state='leased'
    and lease_expires_at<=clock_timestamp() and expires_at>clock_timestamp();

  select * into e
  from public.companion_concierge_completion_outbox x
  where x.user_id=p_user_id and x.summary_state='ready-to-surface'
    and x.expires_at>clock_timestamp()
  order by x.created_at
  for update skip locked
  limit 1;

  if not found then return jsonb_build_object('available',false); end if;

  select * into j
  from public.companion_foundation_pending_jobs p
  where p.job_id=e.concierge_request_id
    and p.user_id=p_user_id;

  if not found
     or j.synthesis_status<>'ready'
     or j.final_answer is null
     or j.final_answer_sha256 is null then
    return jsonb_build_object(
      'available',false,
      'reasonCode','completion-answer-not-ready'
    );
  end if;

  update public.companion_concierge_completion_outbox
  set summary_state='leased',lease_token=token,
      lease_expires_at=clock_timestamp()+interval '5 minutes'
  where event_id=e.event_id;

  return jsonb_build_object(
    'available',true,'eventId',e.event_id,'leaseToken',token,
    'leaseExpiresAt',clock_timestamp()+interval '5 minutes',
    'requestId',e.concierge_request_id,'eventType',e.event_type,
    'capabilityIds',to_jsonb(e.capability_ids),'reasonCode',e.reason_code,
    'sourceConversationId',e.source_conversation_id,
    'sourceMessageId',e.source_message_id,
    'createdAt',e.created_at,'expiresAt',e.expires_at,
    'finalAnswer',j.final_answer,
    'finalAnswerSha256',j.final_answer_sha256,
    'resultPacketSha256',j.final_result_sha256,
    'synthesisStatus',j.synthesis_status
  );
end;
$function$;
