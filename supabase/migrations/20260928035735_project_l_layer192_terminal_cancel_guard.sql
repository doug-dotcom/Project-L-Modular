create or replace function public.companion_cancel_local_concierge_job_v2(
  p_user_id uuid,
  p_request_id uuid,
  p_reason_code text,
  p_superseded_by_request_id uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public'
as $function$
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

  if j.status in ('completed','failed') then
    return jsonb_build_object('status',j.status,'requestId',p_request_id);
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

  if j.status not in ('ready','waiting-consent') then
    raise exception 'local-concierge-state-not-cancellable' using errcode='22023';
  end if;

  update public.companion_foundation_pending_jobs
  set status='cancelled',
      cancellation_reason=p_reason_code,
      superseded_by_request_id=p_superseded_by_request_id,
      cancelled_at=now_at,
      completed_at=coalesce(completed_at,now_at),
      synthesis_status=case when synthesis_status='ready' then synthesis_status else 'failed' end,
      updated_at=now_at
  where job_id=p_request_id and user_id=p_user_id;

  delete from public.companion_concierge_completion_outbox
  where user_id=p_user_id
    and concierge_request_id=p_request_id
    and summary_state in ('ready-to-surface','leased');

  return jsonb_build_object(
    'status','cancelled','requestId',p_request_id,
    'reasonCode',p_reason_code,
    'supersededByRequestId',p_superseded_by_request_id,
    'cancelledAt',now_at
  );
end;
$function$;
