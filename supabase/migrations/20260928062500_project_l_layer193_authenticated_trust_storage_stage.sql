-- Layer 193 stage 1: authenticated trust-state envelope storage.
-- v2 RPCs remain executable during the code cutover. Layer 193 will revoke
-- them only after the v3 runtime has deployed successfully.

alter table public.shine_ai_trace_trust_state
    add column if not exists state_sha256 text,
    add column if not exists storage_auth_key_id text,
    add column if not exists storage_auth_tag text;

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conname = 'shine_ai_trace_trust_state_state_sha256_ck'
    ) then
        alter table public.shine_ai_trace_trust_state
            add constraint shine_ai_trace_trust_state_state_sha256_ck
            check (
                state_sha256 is null
                or state_sha256 ~ '^[a-f0-9]{64}$'
            );
    end if;
    if not exists (
        select 1 from pg_constraint
        where conname = 'shine_ai_trace_trust_state_auth_key_id_ck'
    ) then
        alter table public.shine_ai_trace_trust_state
            add constraint shine_ai_trace_trust_state_auth_key_id_ck
            check (
                storage_auth_key_id is null
                or storage_auth_key_id ~ '^[a-z0-9][a-z0-9._-]{0,63}$'
            );
    end if;
    if not exists (
        select 1 from pg_constraint
        where conname = 'shine_ai_trace_trust_state_auth_tag_ck'
    ) then
        alter table public.shine_ai_trace_trust_state
            add constraint shine_ai_trace_trust_state_auth_tag_ck
            check (
                storage_auth_tag is null
                or storage_auth_tag ~ '^[a-f0-9]{64}$'
            );
    end if;
end $$;

create or replace function public.shine_ai_trace_trust_snapshot_v3()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    base jsonb;
    state_row public.shine_ai_trace_trust_state%rowtype;
begin
    base := public.shine_ai_trace_trust_snapshot_v2();
    if base->>'status' <> 'trusted' then
        return base;
    end if;

    select *
    into state_row
    from public.shine_ai_trace_trust_state
    where singleton = true;

    if state_row.state_sha256 is null
       or state_row.storage_auth_key_id is null
       or state_row.storage_auth_tag is null then
        return base || jsonb_build_object(
            'status','unsealed',
            'reason_code','trust-state-authentication-missing'
        );
    end if;

    return base || jsonb_build_object(
        'state_sha256',state_row.state_sha256,
        'storage_auth_key_id',state_row.storage_auth_key_id,
        'storage_auth_tag',state_row.storage_auth_tag
    );
end;
$$;

create or replace function public.shine_ai_trace_trust_seal_v3(
    p_expected_generation integer,
    p_expected_keyset_sha256 text,
    p_expected_trusted_keyset jsonb,
    p_state_sha256 text,
    p_storage_auth_key_id text,
    p_storage_auth_tag text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    base jsonb;
    row_state public.shine_ai_trace_trust_state%rowtype;
begin
    perform pg_advisory_xact_lock(hashtext('shine-ai-trace-trust-v3'));
    base := public.shine_ai_trace_trust_snapshot_v2();

    if base->>'status' <> 'trusted' then
        raise exception 'trace trust state unavailable for sealing';
    end if;
    if (base->>'generation')::integer <> p_expected_generation
       or base->>'keyset_sha256' <> p_expected_keyset_sha256
       or base->'trusted_keyset' <> p_expected_trusted_keyset then
        raise exception 'trace trust seal precondition mismatch';
    end if;
    if p_state_sha256 !~ '^[a-f0-9]{64}$'
       or p_storage_auth_key_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
       or p_storage_auth_tag !~ '^[a-f0-9]{64}$' then
        raise exception 'trace trust seal invalid';
    end if;

    select *
    into row_state
    from public.shine_ai_trace_trust_state
    where singleton = true
    for update;

    if row_state.state_sha256 is not null then
        if row_state.state_sha256 = p_state_sha256
           and row_state.storage_auth_key_id = p_storage_auth_key_id
           and row_state.storage_auth_tag = p_storage_auth_tag then
            return jsonb_build_object(
                'status','already_sealed',
                'generation',row_state.generation,
                'keyset_sha256',row_state.keyset_sha256
            );
        end if;
        raise exception 'trace trust state already sealed differently';
    end if;

    update public.shine_ai_trace_trust_state
    set state_sha256 = p_state_sha256,
        storage_auth_key_id = p_storage_auth_key_id,
        storage_auth_tag = p_storage_auth_tag,
        updated_at = now()
    where singleton = true;

    return jsonb_build_object(
        'status','sealed',
        'generation',p_expected_generation,
        'keyset_sha256',p_expected_keyset_sha256
    );
end;
$$;

create or replace function public.shine_ai_trace_trust_bootstrap_v3(
    p_generation integer,
    p_keyset_sha256 text,
    p_trusted_keyset jsonb,
    p_state_sha256 text,
    p_storage_auth_key_id text,
    p_storage_auth_tag text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    result jsonb;
begin
    perform pg_advisory_xact_lock(hashtext('shine-ai-trace-trust-v3'));

    result := public.shine_ai_trace_trust_bootstrap_v2(
        p_generation,
        p_keyset_sha256,
        p_trusted_keyset
    );

    update public.shine_ai_trace_trust_state
    set state_sha256 = p_state_sha256,
        storage_auth_key_id = p_storage_auth_key_id,
        storage_auth_tag = p_storage_auth_tag,
        updated_at = now()
    where singleton = true
      and generation = p_generation
      and keyset_sha256 = p_keyset_sha256
      and trusted_keyset = p_trusted_keyset;

    if not found then
        raise exception 'trace trust v3 bootstrap authentication commit failed';
    end if;

    return result;
end;
$$;

create or replace function public.shine_ai_trace_trust_observe_v3(
    p_expected_generation integer,
    p_expected_keyset_sha256 text,
    p_trusted_keyset jsonb,
    p_state_sha256 text,
    p_storage_auth_key_id text,
    p_storage_auth_tag text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    base jsonb;
begin
    perform pg_advisory_xact_lock(hashtext('shine-ai-trace-trust-v3'));

    base := public.shine_ai_trace_trust_snapshot_v2();
    if base->>'status' <> 'trusted' then
        raise exception 'trace trust storage inconsistent';
    end if;
    if (base->>'generation')::integer <> p_expected_generation
       or base->>'keyset_sha256' <> p_expected_keyset_sha256 then
        raise exception 'trace trust observation anti-rollback mismatch';
    end if;
    if p_trusted_keyset->>'keyset_sha256' <> p_expected_keyset_sha256
       or (p_trusted_keyset->>'generation')::integer <> p_expected_generation then
        raise exception 'trace trust observation keyset mismatch';
    end if;
    if p_state_sha256 !~ '^[a-f0-9]{64}$'
       or p_storage_auth_key_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
       or p_storage_auth_tag !~ '^[a-f0-9]{64}$' then
        raise exception 'trace trust observation authentication invalid';
    end if;

    update public.shine_ai_trace_trust_state
    set trusted_keyset = p_trusted_keyset,
        state_sha256 = p_state_sha256,
        storage_auth_key_id = p_storage_auth_key_id,
        storage_auth_tag = p_storage_auth_tag,
        updated_at = now()
    where singleton = true
      and generation = p_expected_generation
      and keyset_sha256 = p_expected_keyset_sha256;

    if not found then
        raise exception 'trace trust observation commit failed';
    end if;

    return jsonb_build_object(
        'status','observed',
        'generation',p_expected_generation,
        'keyset_sha256',p_expected_keyset_sha256
    );
end;
$$;

create or replace function public.shine_ai_trace_trust_advance_v3(
    p_expected_generation integer,
    p_expected_keyset_sha256 text,
    p_next_generation integer,
    p_next_keyset_sha256 text,
    p_next_trusted_keyset jsonb,
    p_authorization_key_id text,
    p_authorization_public_key_sha256 text,
    p_certificate_sha256 text,
    p_state_sha256 text,
    p_storage_auth_key_id text,
    p_storage_auth_tag text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    result jsonb;
begin
    perform pg_advisory_xact_lock(hashtext('shine-ai-trace-trust-v3'));

    result := public.shine_ai_trace_trust_advance_v2(
        p_expected_generation,
        p_expected_keyset_sha256,
        p_next_generation,
        p_next_keyset_sha256,
        p_next_trusted_keyset,
        p_authorization_key_id,
        p_authorization_public_key_sha256,
        p_certificate_sha256
    );

    update public.shine_ai_trace_trust_state
    set state_sha256 = p_state_sha256,
        storage_auth_key_id = p_storage_auth_key_id,
        storage_auth_tag = p_storage_auth_tag,
        updated_at = now()
    where singleton = true
      and generation = p_next_generation
      and keyset_sha256 = p_next_keyset_sha256
      and trusted_keyset = p_next_trusted_keyset;

    if not found then
        raise exception 'trace trust v3 advance authentication commit failed';
    end if;

    return result;
end;
$$;

revoke all on function public.shine_ai_trace_trust_snapshot_v3()
    from public, anon, authenticated;
revoke all on function public.shine_ai_trace_trust_seal_v3(integer,text,jsonb,text,text,text)
    from public, anon, authenticated;
revoke all on function public.shine_ai_trace_trust_bootstrap_v3(integer,text,jsonb,text,text,text)
    from public, anon, authenticated;
revoke all on function public.shine_ai_trace_trust_observe_v3(integer,text,jsonb,text,text,text)
    from public, anon, authenticated;
revoke all on function public.shine_ai_trace_trust_advance_v3(integer,text,integer,text,jsonb,text,text,text,text,text,text)
    from public, anon, authenticated;

grant execute on function public.shine_ai_trace_trust_snapshot_v3()
    to service_role;
grant execute on function public.shine_ai_trace_trust_seal_v3(integer,text,jsonb,text,text,text)
    to service_role;
grant execute on function public.shine_ai_trace_trust_bootstrap_v3(integer,text,jsonb,text,text,text)
    to service_role;
grant execute on function public.shine_ai_trace_trust_observe_v3(integer,text,jsonb,text,text,text)
    to service_role;
grant execute on function public.shine_ai_trace_trust_advance_v3(integer,text,integer,text,jsonb,text,text,text,text,text,text)
    to service_role;
