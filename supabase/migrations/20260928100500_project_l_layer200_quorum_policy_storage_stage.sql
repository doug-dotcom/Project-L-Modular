-- Layer 200 stage 1: authenticated witness-quorum policy storage.
-- The quorum policy itself is immutable in this layer. Only its storage HMAC
-- wrapper may be sealed/rotated. v1 bootstrap remains during staged cutover.

alter table public.shine_ai_witness_quorum_policy_state
    add column if not exists state_sha256 text,
    add column if not exists storage_auth_key_id text,
    add column if not exists storage_auth_tag text;

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conname = 'shine_ai_witness_quorum_policy_state_sha_ck'
    ) then
        alter table public.shine_ai_witness_quorum_policy_state
            add constraint shine_ai_witness_quorum_policy_state_sha_ck
            check (
                state_sha256 is null
                or state_sha256 ~ '^[a-f0-9]{64}$'
            );
    end if;
    if not exists (
        select 1 from pg_constraint
        where conname = 'shine_ai_witness_quorum_policy_auth_key_ck'
    ) then
        alter table public.shine_ai_witness_quorum_policy_state
            add constraint shine_ai_witness_quorum_policy_auth_key_ck
            check (
                storage_auth_key_id is null
                or storage_auth_key_id ~ '^[a-z0-9][a-z0-9._-]{0,63}$'
            );
    end if;
    if not exists (
        select 1 from pg_constraint
        where conname = 'shine_ai_witness_quorum_policy_auth_tag_ck'
    ) then
        alter table public.shine_ai_witness_quorum_policy_state
            add constraint shine_ai_witness_quorum_policy_auth_tag_ck
            check (
                storage_auth_tag is null
                or storage_auth_tag ~ '^[a-f0-9]{64}$'
            );
    end if;
end $$;

create table if not exists public.shine_ai_witness_quorum_policy_storage_rotation_ledger (
    id bigint generated always as identity primary key,
    generation integer not null check (generation >= 1),
    policy_sha256 text not null check (policy_sha256 ~ '^[a-f0-9]{64}$'),
    state_sha256 text not null check (state_sha256 ~ '^[a-f0-9]{64}$'),
    source_envelope_auth_key_id text not null
        check (source_envelope_auth_key_id ~ '^[a-z0-9][a-z0-9._-]{0,63}$'),
    source_checkpoint_auth_key_id text not null
        check (source_checkpoint_auth_key_id ~ '^[a-z0-9][a-z0-9._-]{0,63}$'),
    target_auth_key_id text not null
        check (target_auth_key_id ~ '^[a-z0-9][a-z0-9._-]{0,63}$'),
    rotated_at timestamptz not null default now()
);

alter table public.shine_ai_witness_quorum_policy_storage_rotation_ledger
    enable row level security;
revoke all on public.shine_ai_witness_quorum_policy_storage_rotation_ledger
    from anon, authenticated;
grant select on public.shine_ai_witness_quorum_policy_storage_rotation_ledger
    to service_role;
drop policy if exists "service role reads witness quorum policy storage rotations"
    on public.shine_ai_witness_quorum_policy_storage_rotation_ledger;
create policy "service role reads witness quorum policy storage rotations"
    on public.shine_ai_witness_quorum_policy_storage_rotation_ledger
    for select to service_role using (true);

create or replace function public.shine_ai_witness_quorum_policy_snapshot_v2()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    base jsonb;
    row_state public.shine_ai_witness_quorum_policy_state%rowtype;
begin
    base := public.shine_ai_witness_quorum_policy_snapshot_v1();
    if base->>'status' <> 'trusted' then
        return base;
    end if;

    select *
    into row_state
    from public.shine_ai_witness_quorum_policy_state
    where singleton=true;

    if row_state.state_sha256 is null
       or row_state.storage_auth_key_id is null
       or row_state.storage_auth_tag is null then
        return base || jsonb_build_object(
            'status','unsealed',
            'reason_code','witness-quorum-policy-storage-authentication-missing'
        );
    end if;

    return base || jsonb_build_object(
        'state_sha256',row_state.state_sha256,
        'storage_auth_key_id',row_state.storage_auth_key_id,
        'storage_auth_tag',row_state.storage_auth_tag
    );
end;
$$;

create or replace function public.shine_ai_witness_quorum_policy_bootstrap_v2(
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
    perform pg_advisory_xact_lock(
      hashtext('shine-ai-witness-quorum-policy-storage-v2')
    );

    if p_state_sha256 !~ '^[a-f0-9]{64}$'
       or p_storage_auth_key_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
       or p_storage_auth_tag !~ '^[a-f0-9]{64}$' then
        raise exception 'witness quorum policy storage authentication invalid';
    end if;

    result := public.shine_ai_witness_quorum_policy_bootstrap_v1();

    update public.shine_ai_witness_quorum_policy_state
    set state_sha256=p_state_sha256,
        storage_auth_key_id=p_storage_auth_key_id,
        storage_auth_tag=p_storage_auth_tag,
        updated_at=now()
    where singleton=true
      and generation=1
      and minimum_witnesses=2
      and accepted_witness_ids=array['foundation-project-l','redis-project-l']::text[]
      and previous_policy_sha256 is null
      and policy_sha256=
        '26b6d1a3b4183cfa596f8c9c06c18e73aa0eda6a80a6362649130e9357bf220e';

    if not found then
        raise exception 'witness quorum policy authenticated bootstrap commit failed';
    end if;

    return result;
end;
$$;

create or replace function public.shine_ai_witness_quorum_policy_seal_v2(
    p_expected_generation integer,
    p_expected_policy_sha256 text,
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
    snapshot jsonb;
    row_state public.shine_ai_witness_quorum_policy_state%rowtype;
begin
    perform pg_advisory_xact_lock(
      hashtext('shine-ai-witness-quorum-policy-storage-v2')
    );
    snapshot := public.shine_ai_witness_quorum_policy_snapshot_v1();
    if snapshot->>'status' <> 'trusted' then
        raise exception 'witness quorum policy state unavailable for sealing';
    end if;
    if (snapshot->'trust_state'->>'generation')::integer <> p_expected_generation
       or snapshot->'trust_state'->>'policySha256' <> p_expected_policy_sha256 then
        raise exception 'witness quorum policy seal precondition mismatch';
    end if;
    if p_state_sha256 !~ '^[a-f0-9]{64}$'
       or p_storage_auth_key_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
       or p_storage_auth_tag !~ '^[a-f0-9]{64}$' then
        raise exception 'witness quorum policy seal invalid';
    end if;

    select *
    into row_state
    from public.shine_ai_witness_quorum_policy_state
    where singleton=true
    for update;

    if row_state.state_sha256 is not null then
        if row_state.state_sha256=p_state_sha256
           and row_state.storage_auth_key_id=p_storage_auth_key_id
           and row_state.storage_auth_tag=p_storage_auth_tag then
            return jsonb_build_object(
                'status','already_sealed',
                'generation',row_state.generation,
                'policy_sha256',row_state.policy_sha256
            );
        end if;
        raise exception 'witness quorum policy already sealed differently';
    end if;

    update public.shine_ai_witness_quorum_policy_state
    set state_sha256=p_state_sha256,
        storage_auth_key_id=p_storage_auth_key_id,
        storage_auth_tag=p_storage_auth_tag,
        updated_at=now()
    where singleton=true;

    return jsonb_build_object(
        'status','sealed',
        'generation',p_expected_generation,
        'policy_sha256',p_expected_policy_sha256
    );
end;
$$;

create or replace function public.shine_ai_witness_quorum_policy_rotate_storage_v2(
    p_expected_generation integer,
    p_expected_policy_sha256 text,
    p_expected_state_sha256 text,
    p_source_envelope_auth_key_id text,
    p_source_checkpoint_auth_key_id text,
    p_target_auth_key_id text,
    p_storage_auth_tag text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    row_state public.shine_ai_witness_quorum_policy_state%rowtype;
begin
    perform pg_advisory_xact_lock(
      hashtext('shine-ai-witness-quorum-policy-storage-v2')
    );

    if p_expected_generation < 1
       or p_expected_policy_sha256 !~ '^[a-f0-9]{64}$'
       or p_expected_state_sha256 !~ '^[a-f0-9]{64}$'
       or p_source_envelope_auth_key_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
       or p_source_checkpoint_auth_key_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
       or p_target_auth_key_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
       or p_storage_auth_tag !~ '^[a-f0-9]{64}$' then
        raise exception 'witness quorum policy storage rotation invalid';
    end if;

    select *
    into row_state
    from public.shine_ai_witness_quorum_policy_state
    where singleton=true
    for update;

    if not found
       or row_state.generation <> p_expected_generation
       or row_state.policy_sha256 <> p_expected_policy_sha256
       or row_state.state_sha256 <> p_expected_state_sha256 then
        raise exception 'witness quorum policy storage rotation precondition mismatch';
    end if;

    if row_state.storage_auth_key_id = p_target_auth_key_id then
        if row_state.storage_auth_tag = p_storage_auth_tag then
            return jsonb_build_object(
                'status','already_rotated',
                'generation',row_state.generation,
                'policy_sha256',row_state.policy_sha256,
                'storage_auth_key_id',row_state.storage_auth_key_id
            );
        end if;
        raise exception 'witness quorum policy target key tag mismatch';
    end if;

    if row_state.storage_auth_key_id <> p_source_envelope_auth_key_id then
        raise exception 'witness quorum policy source envelope key mismatch';
    end if;

    update public.shine_ai_witness_quorum_policy_state
    set storage_auth_key_id=p_target_auth_key_id,
        storage_auth_tag=p_storage_auth_tag,
        updated_at=now()
    where singleton=true;

    insert into public.shine_ai_witness_quorum_policy_storage_rotation_ledger (
        generation,
        policy_sha256,
        state_sha256,
        source_envelope_auth_key_id,
        source_checkpoint_auth_key_id,
        target_auth_key_id
    ) values (
        p_expected_generation,
        p_expected_policy_sha256,
        p_expected_state_sha256,
        p_source_envelope_auth_key_id,
        p_source_checkpoint_auth_key_id,
        p_target_auth_key_id
    );

    return jsonb_build_object(
        'status','rotated',
        'generation',p_expected_generation,
        'policy_sha256',p_expected_policy_sha256,
        'storage_auth_key_id',p_target_auth_key_id
    );
end;
$$;

revoke all on function public.shine_ai_witness_quorum_policy_snapshot_v2()
    from public, anon, authenticated;
revoke all on function public.shine_ai_witness_quorum_policy_bootstrap_v2(text,text,text)
    from public, anon, authenticated;
revoke all on function public.shine_ai_witness_quorum_policy_seal_v2(integer,text,text,text,text)
    from public, anon, authenticated;
revoke all on function public.shine_ai_witness_quorum_policy_rotate_storage_v2(integer,text,text,text,text,text,text)
    from public, anon, authenticated;

grant execute on function public.shine_ai_witness_quorum_policy_snapshot_v2()
    to service_role;
grant execute on function public.shine_ai_witness_quorum_policy_bootstrap_v2(text,text,text)
    to service_role;
grant execute on function public.shine_ai_witness_quorum_policy_seal_v2(integer,text,text,text,text)
    to service_role;
grant execute on function public.shine_ai_witness_quorum_policy_rotate_storage_v2(integer,text,text,text,text,text,text)
    to service_role;
