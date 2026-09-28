alter table public.companion_foundation_pending_jobs
  drop constraint if exists companion_foundation_pending_jobs_status_check;

alter table public.companion_foundation_pending_jobs
  add constraint companion_foundation_pending_jobs_status_check
  check (status in (
    'waiting-consent','ready','cancelling','completed','failed','cancelled'
  ));

drop index if exists public.companion_pending_jobs_supersession_lookup_idx;
create index companion_pending_jobs_supersession_lookup_idx
  on public.companion_foundation_pending_jobs(
    user_id,source_conversation_id,work_fingerprint,created_at desc
  )
  where status in ('ready','cancelling')
    and work_fingerprint is not null;

create or replace function public.companion_begin_local_concierge_cancel_v1(
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
$function$;

create or replace function public.companion_finish_local_concierge_cancel_v1(
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
  select * into j
  from public.companion_foundation_pending_jobs x
  where x.job_id=p_request_id and x.user_id=p_user_id
  for update;

  if not found then
    return jsonb_build_object('status','not-found','requestId',p_request_id);
  end if;

  if j.status='cancelled'
     and j.cancellation_reason=p_reason_code
     and j.superseded_by_request_id is not distinct from p_superseded_by_request_id then
    return jsonb_build_object(
      'status','already-cancelled','requestId',p_request_id,
      'reasonCode',j.cancellation_reason,
      'supersededByRequestId',j.superseded_by_request_id,
      'cancelledAt',j.cancelled_at
    );
  end if;

  if j.status<>'cancelling'
     or j.cancellation_reason is distinct from p_reason_code
     or j.superseded_by_request_id is distinct from p_superseded_by_request_id then
    raise exception 'local-concierge-cancellation-finish-mismatch' using errcode='22023';
  end if;

  update public.companion_foundation_pending_jobs
  set status='cancelled',
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

revoke all on function public.companion_begin_local_concierge_cancel_v1(uuid,uuid,text,uuid)
  from public,anon,authenticated;
grant execute on function public.companion_begin_local_concierge_cancel_v1(uuid,uuid,text,uuid)
  to service_role;

revoke all on function public.companion_finish_local_concierge_cancel_v1(uuid,uuid,text,uuid)
  from public,anon,authenticated;
grant execute on function public.companion_finish_local_concierge_cancel_v1(uuid,uuid,text,uuid)
  to service_role;
