CREATE OR REPLACE FUNCTION public.companion_begin_local_concierge_cancel_v1(p_user_id uuid, p_request_id uuid, p_reason_code text, p_superseded_by_request_id uuid DEFAULT NULL::uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
declare
  j public.companion_foundation_pending_jobs%rowtype;
  now_at timestamptz:=clock_timestamp();
begin
  if p_user_id is null or p_request_id is null
     or p_reason_code is null or length(p_reason_code)<1 or length(p_reason_code)>160
     or p_superseded_by_request_id=p_request_id then
    raise exception 'invalid-local-concierge-cancellation' using errcode='22023';
  end if;

  select * into j
  from public.companion_foundation_pending_jobs x
  where x.job_id=p_request_id and x.user_id=p_user_id
  for update;

  if not found then
    return jsonb_build_object('status','not-found','requestId',p_request_id);
  end if;

  if j.status in ('completed','failed','retired') then
    return jsonb_build_object(
      'status',j.status,
      'requestId',p_request_id,
      'reasonCode',case when j.status='retired' then j.retirement_reason else null end,
      'retiredAt',case when j.status='retired' then j.retired_at else null end,
      'receiptSha256',case when j.status='retired' then j.retirement_receipt_sha256 else null end
    );
  end if;

  if j.status='cancelled' then
    if j.cancellation_reason=p_reason_code
       and j.superseded_by_request_id is not distinct from p_superseded_by_request_id then
      return jsonb_build_object(
        'status','already-cancelled','requestId',p_request_id,
        'reasonCode',j.cancellation_reason,
        'supersededByRequestId',j.superseded_by_request_id,
        'cancelledAt',j.cancelled_at
      );
    end if;
    raise exception 'local-concierge-cancellation-conflict' using errcode='22023';
  end if;

  if j.status='cancelling' then
    if j.cancellation_reason=p_reason_code
       and j.superseded_by_request_id is not distinct from p_superseded_by_request_id then
      return jsonb_build_object(
        'status','cancelling','requestId',p_request_id,
        'reasonCode',j.cancellation_reason,
        'supersededByRequestId',j.superseded_by_request_id
      );
    end if;
    raise exception 'local-concierge-cancellation-conflict' using errcode='22023';
  end if;

  if j.status not in ('ready','waiting-consent') then
    raise exception 'local-concierge-state-not-cancellable' using errcode='22023';
  end if;

  update public.companion_foundation_pending_jobs
  set status='cancelling',
      cancellation_reason=p_reason_code,
      superseded_by_request_id=p_superseded_by_request_id,
      cancelled_at=null,
      updated_at=now_at
  where job_id=p_request_id and user_id=p_user_id;

  delete from public.companion_concierge_completion_outbox
  where user_id=p_user_id
    and concierge_request_id=p_request_id
    and summary_state in ('ready-to-surface','leased');

  return jsonb_build_object(
    'status','cancelling','requestId',p_request_id,
    'reasonCode',p_reason_code,
    'supersededByRequestId',p_superseded_by_request_id
  );
end;
$function$

