alter table public.companion_foundation_pending_jobs
  add column if not exists retirement_reason text,
  add column if not exists retired_at timestamptz,
  add column if not exists retirement_receipt_sha256 text;

alter table public.companion_foundation_pending_jobs
  drop constraint if exists companion_foundation_pending_jobs_status_check,
  add constraint companion_foundation_pending_jobs_status_check
    check (status in (
      'waiting-consent','ready','cancelling','completed',
      'failed','cancelled','retired'
    )),
  drop constraint if exists companion_pending_jobs_retirement_reason,
  add constraint companion_pending_jobs_retirement_reason
    check (retirement_reason is null or length(retirement_reason)<=160),
  drop constraint if exists companion_pending_jobs_retirement_sha256,
  add constraint companion_pending_jobs_retirement_sha256
    check (
      retirement_receipt_sha256 is null
      or retirement_receipt_sha256 ~ '^[a-f0-9]{64}$'
    );

create or replace function public.companion_mark_local_concierge_retired_v1(
  p_user_id uuid,
  p_request_id uuid,
  p_reason_code text,
  p_retired_at timestamptz,
  p_receipt_sha256 text
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public'
as $function$
declare
  j public.companion_foundation_pending_jobs%rowtype;
begin
  if p_user_id is null or p_request_id is null
     or p_reason_code is null or length(p_reason_code)<1 or length(p_reason_code)>160
     or p_retired_at is null
     or p_receipt_sha256 !~ '^[a-f0-9]{64}$' then
    raise exception 'invalid-local-concierge-retirement' using errcode='22023';
  end if;

  select * into j
  from public.companion_foundation_pending_jobs x
  where x.job_id=p_request_id and x.user_id=p_user_id
  for update;

  if not found then
    return jsonb_build_object('status','not-found','requestId',p_request_id);
  end if;

  if j.status='retired' then
    if j.retirement_reason=p_reason_code
       and j.retired_at=p_retired_at
       and j.retirement_receipt_sha256=p_receipt_sha256 then
      return jsonb_build_object('status','already-retired','requestId',p_request_id);
    end if;
    raise exception 'local-concierge-retirement-conflict' using errcode='22023';
  end if;

  if j.status in ('completed','failed','cancelled') then
    return jsonb_build_object('status',j.status,'requestId',p_request_id);
  end if;

  if j.status not in ('waiting-consent','ready','cancelling') then
    raise exception 'local-concierge-state-not-retirable' using errcode='22023';
  end if;

  update public.companion_foundation_pending_jobs
  set status='retired',
      retirement_reason=p_reason_code,
      retired_at=p_retired_at,
      retirement_receipt_sha256=p_receipt_sha256,
      completed_at=coalesce(completed_at,p_retired_at),
      synthesis_status=case when synthesis_status='ready' then synthesis_status else 'failed' end,
      updated_at=clock_timestamp()
  where job_id=p_request_id and user_id=p_user_id;

  delete from public.companion_concierge_completion_outbox
  where user_id=p_user_id
    and concierge_request_id=p_request_id
    and summary_state in ('ready-to-surface','leased');

  return jsonb_build_object(
    'status','retired',
    'requestId',p_request_id,
    'reasonCode',p_reason_code,
    'retiredAt',p_retired_at,
    'receiptSha256',p_receipt_sha256
  );
end;
$function$;

revoke all on function public.companion_mark_local_concierge_retired_v1(
  uuid,uuid,text,timestamptz,text
) from public, anon, authenticated;
grant execute on function public.companion_mark_local_concierge_retired_v1(
  uuid,uuid,text,timestamptz,text
) to service_role;
