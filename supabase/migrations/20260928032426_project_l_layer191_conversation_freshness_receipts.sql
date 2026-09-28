alter table public.companion_foundation_pending_jobs
  add column if not exists final_answer_generated_at timestamptz;

alter table private.companion_concierge_synthesis_evidence
  add column if not exists temporal_receipt jsonb,
  add column if not exists synthesised_at timestamptz;

alter table private.companion_concierge_synthesis_evidence
  drop constraint if exists companion_concierge_synthesis_temporal_receipt_object,
  add constraint companion_concierge_synthesis_temporal_receipt_object
    check (temporal_receipt is null or jsonb_typeof(temporal_receipt)='object');

create or replace function public.companion_store_delayed_synthesis_answer_v2(
  p_user_id uuid,
  p_request_id uuid,
  p_packet_sha256 text,
  p_answer text,
  p_answer_sha256 text,
  p_temporal_receipt jsonb,
  p_generated_at timestamptz
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','private'
as $function$
declare
  j public.companion_foundation_pending_jobs%rowtype;
  e private.companion_concierge_synthesis_evidence%rowtype;
begin
  if p_user_id is null or p_request_id is null
     or p_packet_sha256 !~ '^[a-f0-9]{64}$'
     or p_answer is null or length(p_answer)<1 or length(p_answer)>50000
     or p_answer_sha256 !~ '^[a-f0-9]{64}$'
     or p_generated_at is null
     or (p_temporal_receipt is not null and jsonb_typeof(p_temporal_receipt)<>'object') then
    raise exception 'invalid-delayed-synthesis-answer' using errcode='22023';
  end if;

  select * into j
  from public.companion_foundation_pending_jobs x
  where x.job_id=p_request_id and x.user_id=p_user_id
  for update;

  if not found then
    raise exception 'delayed-synthesis-job-not-found' using errcode='22023';
  end if;

  select * into e
  from private.companion_concierge_synthesis_evidence x
  where x.request_id=p_request_id and x.user_id=p_user_id
  for update;

  if not found
     or e.result_sha256<>p_packet_sha256
     or j.final_result_sha256<>p_packet_sha256 then
    raise exception 'delayed-synthesis-packet-binding-mismatch' using errcode='22023';
  end if;

  if j.synthesis_status='ready' then
    if j.final_answer=p_answer
       and j.final_answer_sha256=p_answer_sha256
       and j.final_answer_generated_at=p_generated_at
       and e.temporal_receipt is not distinct from p_temporal_receipt
       and e.synthesised_at=p_generated_at then
      return jsonb_build_object(
        'stored',true,'replayed',true,'requestId',p_request_id,
        'answerSha256',p_answer_sha256,'synthesisStatus','ready',
        'generatedAt',p_generated_at
      );
    end if;
    raise exception 'delayed-synthesis-answer-conflict' using errcode='22023';
  end if;

  update private.companion_concierge_synthesis_evidence
  set temporal_receipt=p_temporal_receipt,
      synthesised_at=p_generated_at,
      updated_at=clock_timestamp()
  where request_id=p_request_id and user_id=p_user_id;

  update public.companion_foundation_pending_jobs
  set final_answer=p_answer,
      final_answer_sha256=p_answer_sha256,
      final_answer_generated_at=p_generated_at,
      synthesis_status='ready',
      updated_at=clock_timestamp()
  where job_id=p_request_id and user_id=p_user_id;

  return jsonb_build_object(
    'stored',true,'replayed',false,'requestId',p_request_id,
    'answerSha256',p_answer_sha256,'synthesisStatus','ready',
    'generatedAt',p_generated_at
  );
end;
$function$;

create or replace function public.companion_delayed_synthesis_state_v1(
  p_user_id uuid,
  p_request_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','private'
as $function$
declare
  j public.companion_foundation_pending_jobs%rowtype;
  e private.companion_concierge_synthesis_evidence%rowtype;
begin
  select * into j
  from public.companion_foundation_pending_jobs x
  where x.job_id=p_request_id and x.user_id=p_user_id;

  if not found then
    return jsonb_build_object('found',false);
  end if;

  select * into e
  from private.companion_concierge_synthesis_evidence x
  where x.request_id=p_request_id and x.user_id=p_user_id;

  return jsonb_build_object(
    'found',true,
    'requestId',j.job_id,
    'requestText',j.request_text,
    'sourceConversationId',j.source_conversation_id,
    'sourceMessageId',j.source_message_id,
    'synthesisStatus',j.synthesis_status,
    'packetSha256',j.final_result_sha256,
    'resultPacket',case when e.request_id is null then null else e.result_packet end,
    'temporalReceipt',case when e.request_id is null then null else e.temporal_receipt end,
    'finalAnswer',j.final_answer,
    'finalAnswerSha256',j.final_answer_sha256,
    'finalAnswerGeneratedAt',j.final_answer_generated_at
  );
end;
$function$;

create or replace function public.companion_delayed_completion_history_v1(
  p_user_id uuid,
  p_limit integer
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','private'
as $function$
declare result jsonb;
begin
  if p_user_id is null or p_limit is null or p_limit<1 or p_limit>100 then
    raise exception 'invalid-delayed-completion-history-request' using errcode='22023';
  end if;

  select coalesce(jsonb_agg(
    jsonb_build_object(
      'requestId',j.job_id,
      'sourceConversationId',j.source_conversation_id,
      'sourceMessageId',j.source_message_id,
      'requestText',j.request_text,
      'completedAt',j.completed_at,
      'updatedAt',j.updated_at,
      'packetSha256',j.final_result_sha256,
      'finalAnswer',j.final_answer,
      'finalAnswerSha256',j.final_answer_sha256,
      'finalAnswerGeneratedAt',j.final_answer_generated_at,
      'temporalReceipt',e.temporal_receipt
    )
    order by j.updated_at desc
  ),'[]'::jsonb)
  into result
  from (
    select *
    from public.companion_foundation_pending_jobs
    where user_id=p_user_id
      and status='completed'
      and synthesis_status='ready'
    order by updated_at desc
    limit p_limit
  ) j
  join private.companion_concierge_synthesis_evidence e
    on e.request_id=j.job_id and e.user_id=j.user_id;

  return jsonb_build_object(
    'status','ok',
    'version','1.0',
    'items',result
  );
end;
$function$;

create or replace function public.companion_claim_completion_event_v3(
  p_user_id uuid,
  p_source_conversation_id text
)
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

  if p_source_conversation_id is not null
     and (length(p_source_conversation_id)<1 or length(p_source_conversation_id)>180) then
    raise exception 'invalid-source-conversation-id' using errcode='22023';
  end if;

  update public.companion_concierge_completion_outbox
  set summary_state='ready-to-surface',lease_token=null,lease_expires_at=null
  where user_id=p_user_id and summary_state='leased'
    and lease_expires_at<=clock_timestamp() and expires_at>clock_timestamp();

  select * into e
  from public.companion_concierge_completion_outbox x
  where x.user_id=p_user_id
    and x.summary_state='ready-to-surface'
    and x.expires_at>clock_timestamp()
    and (
      p_source_conversation_id is null
      or x.source_conversation_id=p_source_conversation_id
    )
  order by x.created_at
  for update skip locked
  limit 1;

  if not found then return jsonb_build_object('available',false); end if;

  select * into j
  from public.companion_foundation_pending_jobs p
  where p.job_id=e.concierge_request_id
    and p.user_id=p_user_id;

  if e.event_type='retry-completed' and (
       not found
       or j.synthesis_status<>'ready'
       or j.final_answer is null
       or j.final_answer_sha256 is null
       or j.final_answer_generated_at is null
     ) then
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
    'finalAnswer',case when j.synthesis_status='ready' then j.final_answer else null end,
    'finalAnswerSha256',case when j.synthesis_status='ready' then j.final_answer_sha256 else null end,
    'finalAnswerGeneratedAt',j.final_answer_generated_at,
    'resultPacketSha256',j.final_result_sha256,
    'synthesisStatus',j.synthesis_status
  );
end;
$function$;

revoke all on function public.companion_store_delayed_synthesis_answer_v2(uuid,uuid,text,text,text,jsonb,timestamptz)
  from public, anon, authenticated;
grant execute on function public.companion_store_delayed_synthesis_answer_v2(uuid,uuid,text,text,text,jsonb,timestamptz)
  to service_role;

revoke all on function public.companion_delayed_completion_history_v1(uuid,integer)
  from public, anon, authenticated;
grant execute on function public.companion_delayed_completion_history_v1(uuid,integer)
  to service_role;

revoke all on function public.companion_claim_completion_event_v3(uuid,text)
  from public, anon, authenticated;
grant execute on function public.companion_claim_completion_event_v3(uuid,text)
  to service_role;
