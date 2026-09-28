create or replace function public.companion_store_delayed_synthesis_packet_v1(
  p_user_id uuid,
  p_request_id uuid,
  p_packet jsonb,
  p_packet_sha256 text
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
     or p_packet is null or jsonb_typeof(p_packet)<>'object'
     or p_packet_sha256 is null
     or p_packet_sha256 !~ '^[a-f0-9]{64}$' then
    raise exception 'invalid-delayed-synthesis-packet' using errcode='22023';
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
  where x.request_id=p_request_id
  for update;

  if found and (e.user_id<>p_user_id or e.result_sha256<>p_packet_sha256 or e.result_packet<>p_packet) then
    raise exception 'delayed-synthesis-packet-conflict' using errcode='22023';
  end if;

  if not found then
    insert into private.companion_concierge_synthesis_evidence(
      request_id,user_id,result_packet,result_sha256
    ) values (
      p_request_id,p_user_id,p_packet,p_packet_sha256
    );
  else
    update private.companion_concierge_synthesis_evidence
    set updated_at=clock_timestamp()
    where request_id=p_request_id;
  end if;

  if j.synthesis_status='ready'
     and j.final_result_sha256=p_packet_sha256
     and j.final_answer is not null
     and j.final_answer_sha256 is not null then
    return jsonb_build_object(
      'stored',true,'replayed',true,'requestId',p_request_id,
      'packetSha256',p_packet_sha256,'synthesisStatus','ready'
    );
  end if;

  update public.companion_foundation_pending_jobs
  set final_result_sha256=p_packet_sha256,
      final_answer=null,
      final_answer_sha256=null,
      synthesis_status='pending',
      updated_at=clock_timestamp()
  where job_id=p_request_id and user_id=p_user_id;

  return jsonb_build_object(
    'stored',true,'replayed',false,'requestId',p_request_id,
    'packetSha256',p_packet_sha256,'synthesisStatus','pending'
  );
end;
$function$;

create or replace function public.companion_store_delayed_synthesis_answer_v1(
  p_user_id uuid,
  p_request_id uuid,
  p_packet_sha256 text,
  p_answer text,
  p_answer_sha256 text
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
     or p_packet_sha256 is null
     or p_packet_sha256 !~ '^[a-f0-9]{64}$'
     or p_answer is null or length(p_answer)<1 or length(p_answer)>50000
     or p_answer_sha256 is null
     or p_answer_sha256 !~ '^[a-f0-9]{64}$' then
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
  where x.request_id=p_request_id and x.user_id=p_user_id;

  if not found
     or e.result_sha256<>p_packet_sha256
     or j.final_result_sha256<>p_packet_sha256 then
    raise exception 'delayed-synthesis-packet-binding-mismatch' using errcode='22023';
  end if;

  if j.synthesis_status='ready' then
    if j.final_answer=p_answer and j.final_answer_sha256=p_answer_sha256 then
      return jsonb_build_object(
        'stored',true,'replayed',true,'requestId',p_request_id,
        'answerSha256',p_answer_sha256,'synthesisStatus','ready'
      );
    end if;
    raise exception 'delayed-synthesis-answer-conflict' using errcode='22023';
  end if;

  update public.companion_foundation_pending_jobs
  set final_answer=p_answer,
      final_answer_sha256=p_answer_sha256,
      synthesis_status='ready',
      updated_at=clock_timestamp()
  where job_id=p_request_id and user_id=p_user_id;

  return jsonb_build_object(
    'stored',true,'replayed',false,'requestId',p_request_id,
    'answerSha256',p_answer_sha256,'synthesisStatus','ready'
  );
end;
$function$;
