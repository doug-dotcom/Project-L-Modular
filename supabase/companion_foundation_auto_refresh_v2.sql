-- Native Companion Foundation automatic delegation renewal v2
-- Production migration: companion_foundation_auto_refresh_v2
--
-- Extends the existing owner-bound Companion/Foundation link store with a
-- crash-safe refresh lease and a durable pending rotation. Raw candidate
-- delegation/refresh credentials are created in Supabase Vault before the
-- remote Foundation request. Only hashes and opaque ids leave Shine-L.

alter table public.companion_foundation_links
  add column if not exists refresh_generation integer not null default 1,
  add column if not exists last_refresh_at timestamptz,
  add column if not exists last_refresh_reason text;

create table if not exists private.companion_foundation_refresh_rotations (
  rotation_request_id uuid primary key,
  user_id uuid not null,
  link_request_id uuid not null,
  new_session_id uuid not null unique,
  new_refresh_id uuid not null unique,
  pending_delegation_secret_id uuid not null,
  pending_refresh_secret_id uuid not null,
  new_delegation_token_hash text not null check (new_delegation_token_hash ~ '^[a-fA-F0-9]{64}$'),
  new_refresh_token_hash text not null check (new_refresh_token_hash ~ '^[a-fA-F0-9]{64}$'),
  lease_token uuid not null,
  lease_until timestamptz not null,
  status text not null default 'pending'
    check (status in ('pending','completed','failed')),
  reason_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz,
  foreign key (user_id,link_request_id)
    references public.companion_foundation_links(user_id,request_id)
);

create unique index if not exists companion_foundation_one_pending_refresh_idx
  on private.companion_foundation_refresh_rotations(user_id,link_request_id)
  where status='pending';

create index if not exists companion_foundation_refresh_user_time_idx
  on private.companion_foundation_refresh_rotations(user_id,created_at desc);

revoke all on table private.companion_foundation_refresh_rotations
  from public,anon,authenticated,service_role;

create or replace function public.companion_foundation_connection_state_v2(p_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','private'
as $function$
declare
  l public.companion_foundation_links%rowtype;
begin
  select * into l
  from public.companion_foundation_links
  where user_id=p_user_id
  order by updated_at desc,created_at desc
  limit 1;

  if not found then
    return jsonb_build_object('state','not-connected');
  end if;

  return jsonb_build_object(
    'state',
      case
        when l.link_status<>'exchanged' then 'reconnect-required'
        when l.refresh_expires_at is null or l.refresh_expires_at<=clock_timestamp() then 'reconnect-required'
        when l.delegation_expires_at is not null and l.delegation_expires_at>clock_timestamp() then 'active'
        else 'refresh-required'
      end,
    'requestId',l.request_id,
    'linkStatus',l.link_status,
    'approvedCapabilities',to_jsonb(l.approved_capabilities),
    'delegationExpiresAt',l.delegation_expires_at,
    'refreshExpiresAt',l.refresh_expires_at,
    'refreshGeneration',l.refresh_generation,
    'lastRefreshAt',l.last_refresh_at,
    'lastRefreshReason',l.last_refresh_reason
  );
end;
$function$;

revoke all on function public.companion_foundation_connection_state_v2(uuid)
  from public,anon,authenticated;
grant execute on function public.companion_foundation_connection_state_v2(uuid)
  to service_role;

create or replace function public.companion_claim_foundation_refresh_v2(
  p_user_id uuid,
  p_skew_seconds integer default 300
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','private','vault','extensions'
as $function$
declare
  l public.companion_foundation_links%rowtype;
  r private.companion_foundation_refresh_rotations%rowtype;
  v_now timestamptz:=clock_timestamp();
  v_lease uuid:=gen_random_uuid();
  v_rotation uuid;
  v_session uuid;
  v_refresh_id uuid;
  v_delegation text;
  v_refresh text;
  v_delegation_secret uuid;
  v_refresh_secret uuid;
begin
  if p_user_id is null or p_skew_seconds<0 or p_skew_seconds>3600 then
    raise exception 'invalid-foundation-refresh-claim' using errcode='22023';
  end if;

  select * into l
  from public.companion_foundation_links
  where user_id=p_user_id
  order by updated_at desc,created_at desc
  limit 1
  for update;

  if not found then return jsonb_build_object('state','not-connected'); end if;

  if l.link_status<>'exchanged' then
    return jsonb_build_object('state','reconnect-required','requestId',l.request_id,
                              'reasonCode','local-link-not-exchanged');
  end if;

  if l.refresh_expires_at is null or l.refresh_expires_at<=v_now then
    update public.companion_foundation_links
      set link_status='expired',last_refresh_reason='refresh-expired',updated_at=v_now
    where user_id=l.user_id and request_id=l.request_id;
    return jsonb_build_object('state','reconnect-required','requestId',l.request_id,
                              'reasonCode','refresh-expired');
  end if;

  if l.delegation_expires_at is not null
     and l.delegation_expires_at>v_now+make_interval(secs=>p_skew_seconds) then
    return jsonb_build_object('state','active','requestId',l.request_id,
      'delegationExpiresAt',l.delegation_expires_at,'refreshExpiresAt',l.refresh_expires_at,
      'refreshGeneration',l.refresh_generation);
  end if;

  select * into r
  from private.companion_foundation_refresh_rotations x
  where x.user_id=l.user_id and x.link_request_id=l.request_id and x.status='pending'
  order by x.created_at desc limit 1 for update;

  if found then
    if r.lease_until>v_now then
      return jsonb_build_object('state','busy','requestId',l.request_id,
                                'rotationRequestId',r.rotation_request_id,'retryAfter',r.lease_until);
    end if;
    if not exists(select 1 from vault.secrets where id=r.pending_delegation_secret_id)
       or not exists(select 1 from vault.secrets where id=r.pending_refresh_secret_id) then
      update private.companion_foundation_refresh_rotations
        set status='failed',reason_code='pending-secret-missing',updated_at=v_now
      where rotation_request_id=r.rotation_request_id;
    else
      update private.companion_foundation_refresh_rotations
        set lease_token=v_lease,lease_until=v_now+interval '60 seconds',updated_at=v_now
      where rotation_request_id=r.rotation_request_id;
      return jsonb_build_object(
        'state','refresh-required','requestId',l.request_id,
        'rotationRequestId',r.rotation_request_id,'newSessionId',r.new_session_id,
        'newRefreshId',r.new_refresh_id,'newDelegationTokenHash',r.new_delegation_token_hash,
        'newRefreshTokenHash',r.new_refresh_token_hash,'leaseToken',v_lease,'reusedPending',true);
    end if;
  end if;

  v_rotation:=gen_random_uuid();
  v_session:=gen_random_uuid();
  v_refresh_id:=gen_random_uuid();
  v_delegation:=encode(gen_random_bytes(64),'hex');
  v_refresh:=encode(gen_random_bytes(64),'hex');

  select vault.create_secret(v_delegation,
    'foundation_pending_delegation_'||p_user_id::text||'_'||v_rotation::text,
    'Pending crash-safe Foundation delegation rotation.') into v_delegation_secret;
  select vault.create_secret(v_refresh,
    'foundation_pending_refresh_'||p_user_id::text||'_'||v_rotation::text,
    'Pending crash-safe Foundation refresh rotation.') into v_refresh_secret;

  insert into private.companion_foundation_refresh_rotations(
    rotation_request_id,user_id,link_request_id,new_session_id,new_refresh_id,
    pending_delegation_secret_id,pending_refresh_secret_id,
    new_delegation_token_hash,new_refresh_token_hash,lease_token,lease_until,status,created_at,updated_at
  ) values (
    v_rotation,l.user_id,l.request_id,v_session,v_refresh_id,v_delegation_secret,v_refresh_secret,
    encode(digest(v_delegation,'sha256'),'hex'),encode(digest(v_refresh,'sha256'),'hex'),
    v_lease,v_now+interval '60 seconds','pending',v_now,v_now
  ) returning * into r;

  return jsonb_build_object(
    'state','refresh-required','requestId',l.request_id,
    'rotationRequestId',r.rotation_request_id,'newSessionId',r.new_session_id,
    'newRefreshId',r.new_refresh_id,'newDelegationTokenHash',r.new_delegation_token_hash,
    'newRefreshTokenHash',r.new_refresh_token_hash,'leaseToken',v_lease,'reusedPending',false);
end;
$function$;

revoke all on function public.companion_claim_foundation_refresh_v2(uuid,integer)
  from public,anon,authenticated;
grant execute on function public.companion_claim_foundation_refresh_v2(uuid,integer)
  to service_role;

create or replace function public.companion_complete_foundation_refresh_v2(
  p_user_id uuid,p_rotation_request_id uuid,p_lease_token uuid,
  p_delegation_expires_at timestamptz,p_refresh_expires_at timestamptz,
  p_refresh_generation integer,p_reason_code text
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','private','vault'
as $function$
declare
  r private.companion_foundation_refresh_rotations%rowtype;
  l public.companion_foundation_links%rowtype;
  v_delegation text;
  v_refresh text;
  v_now timestamptz:=clock_timestamp();
begin
  select * into r from private.companion_foundation_refresh_rotations
  where rotation_request_id=p_rotation_request_id and user_id=p_user_id for update;
  if not found then raise exception 'foundation-refresh-rotation-not-found' using errcode='22023'; end if;
  if r.status='completed' then return jsonb_build_object('completed',true,'alreadyCompleted',true); end if;
  if r.status<>'pending' or r.lease_token<>p_lease_token or r.lease_until<=v_now then
    raise exception 'foundation-refresh-lease-invalid' using errcode='22023';
  end if;
  if p_delegation_expires_at<=v_now or p_refresh_expires_at<=p_delegation_expires_at
     or p_refresh_generation<2 then
    raise exception 'invalid-foundation-refresh-result' using errcode='22023';
  end if;

  select * into l from public.companion_foundation_links
  where user_id=p_user_id and request_id=r.link_request_id for update;
  if not found or l.link_status<>'exchanged'
     or l.delegation_secret_id is null or l.refresh_secret_id is null then
    raise exception 'foundation-link-not-refreshable' using errcode='22023';
  end if;

  select decrypted_secret into v_delegation from vault.decrypted_secrets
    where id=r.pending_delegation_secret_id;
  select decrypted_secret into v_refresh from vault.decrypted_secrets
    where id=r.pending_refresh_secret_id;
  if v_delegation is null or v_refresh is null then
    raise exception 'foundation-pending-secret-missing' using errcode='22023';
  end if;

  perform vault.update_secret(l.delegation_secret_id,v_delegation,null,
    'Rotating Foundation delegation for native Shine Companion.',null);
  perform vault.update_secret(l.refresh_secret_id,v_refresh,null,
    'Rotating Foundation refresh credential for native Shine Companion.',null);

  update public.companion_foundation_links
    set delegation_expires_at=p_delegation_expires_at,refresh_expires_at=p_refresh_expires_at,
        refresh_generation=p_refresh_generation,last_refresh_at=v_now,
        last_refresh_reason=left(coalesce(p_reason_code,'delegation-refreshed'),120),updated_at=v_now
  where user_id=p_user_id and request_id=r.link_request_id;

  update private.companion_foundation_refresh_rotations
    set status='completed',reason_code=left(coalesce(p_reason_code,'delegation-refreshed'),120),
        completed_at=v_now,lease_until=v_now,updated_at=v_now
  where rotation_request_id=r.rotation_request_id;

  delete from vault.secrets
  where id in (r.pending_delegation_secret_id,r.pending_refresh_secret_id);

  return jsonb_build_object('completed',true,'alreadyCompleted',false,
    'requestId',r.link_request_id,'refreshGeneration',p_refresh_generation,
    'delegationExpiresAt',p_delegation_expires_at,'refreshExpiresAt',p_refresh_expires_at);
end;
$function$;

revoke all on function public.companion_complete_foundation_refresh_v2(
  uuid,uuid,uuid,timestamptz,timestamptz,integer,text
) from public,anon,authenticated;
grant execute on function public.companion_complete_foundation_refresh_v2(
  uuid,uuid,uuid,timestamptz,timestamptz,integer,text
) to service_role;

create or replace function public.companion_fail_foundation_refresh_v2(
  p_user_id uuid,p_rotation_request_id uuid,p_lease_token uuid,p_reason_code text
)
returns jsonb
language plpgsql
security definer
set search_path to 'pg_catalog','public','private','vault'
as $function$
declare
  r private.companion_foundation_refresh_rotations%rowtype;
  v_now timestamptz:=clock_timestamp();
begin
  select * into r from private.companion_foundation_refresh_rotations
  where rotation_request_id=p_rotation_request_id and user_id=p_user_id for update;
  if not found then return jsonb_build_object('failed',false,'reasonCode','rotation-not-found'); end if;
  if r.status='completed' then return jsonb_build_object('failed',false,'reasonCode','already-completed'); end if;
  if r.status='failed' then return jsonb_build_object('failed',true,'reasonCode',r.reason_code); end if;
  if r.lease_token<>p_lease_token then
    raise exception 'foundation-refresh-lease-invalid' using errcode='22023';
  end if;

  update private.companion_foundation_refresh_rotations
    set status='failed',reason_code=left(coalesce(p_reason_code,'refresh-failed'),120),
        lease_until=v_now,updated_at=v_now
  where rotation_request_id=r.rotation_request_id;

  update public.companion_foundation_links
    set link_status='failed',last_refresh_at=v_now,
        last_refresh_reason=left(coalesce(p_reason_code,'refresh-failed'),120),updated_at=v_now
  where user_id=p_user_id and request_id=r.link_request_id;

  delete from vault.secrets
  where id in (r.pending_delegation_secret_id,r.pending_refresh_secret_id);

  return jsonb_build_object('failed',true,'reasonCode',coalesce(p_reason_code,'refresh-failed'));
end;
$function$;

revoke all on function public.companion_fail_foundation_refresh_v2(uuid,uuid,uuid,text)
  from public,anon,authenticated;
grant execute on function public.companion_fail_foundation_refresh_v2(uuid,uuid,uuid,text)
  to service_role;
