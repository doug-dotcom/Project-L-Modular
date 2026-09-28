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

  select x.* into e
  from public.companion_concierge_completion_outbox x
  where x.user_id=p_user_id
    and x.summary_state='ready-to-surface'
    and x.expires_at>clock_timestamp()
    and (
      x.event_type='retry-abandoned'
      or (
        x.event_type='retry-completed'
        and exists (
          select 1
          from public.companion_foundation_pending_jobs p
          where p.job_id=x.concierge_request_id
            and p.user_id=p_user_id
            and p.synthesis_status='ready'
            and p.final_answer is not null
            and p.final_answer_sha256 is not null
        )
      )
    )
  order by x.created_at
  for update skip locked
  limit 1;

  if not found then return jsonb_build_object('available',false); end if;

  select * into j
  from public.companion_foundation_pending_jobs p
  where p.job_id=e.concierge_request_id
    and p.user_id=p_user_id;

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
    'finalAnswer',case when j.synthesis_status='ready' then j.final_answer else null end,
    'finalAnswerSha256',case when j.synthesis_status='ready' then j.final_answer_sha256 else null end,
    'resultPacketSha256',j.final_result_sha256,
    'synthesisStatus',j.synthesis_status
  );
end;
$function$;
