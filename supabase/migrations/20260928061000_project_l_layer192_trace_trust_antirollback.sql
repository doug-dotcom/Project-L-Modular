-- Layer 192: persisted trust anti-rollback hardening.
-- Runtime service_role becomes read-only on trust tables. Mutations are possible
-- only through monotonic security-definer RPCs that cross-check the append-only
-- ledger high-water mark.

revoke insert, update, delete, truncate, references, trigger
    on public.shine_ai_trace_trust_state from service_role;
revoke insert, update, delete, truncate, references, trigger
    on public.shine_ai_trace_trust_ledger from service_role;
revoke usage, update on sequence public.shine_ai_trace_trust_ledger_id_seq
    from service_role;

grant select on public.shine_ai_trace_trust_state to service_role;
grant select on public.shine_ai_trace_trust_ledger to service_role;
grant select on sequence public.shine_ai_trace_trust_ledger_id_seq to service_role;

drop policy if exists "service role manages shine ai trace trust state"
    on public.shine_ai_trace_trust_state;
drop policy if exists "service role appends shine ai trace trust ledger"
    on public.shine_ai_trace_trust_ledger;

drop policy if exists "service role reads shine ai trace trust state"
    on public.shine_ai_trace_trust_state;
create policy "service role reads shine ai trace trust state"
    on public.shine_ai_trace_trust_state
    for select
    to service_role
    using (true);

drop policy if exists "service role reads shine ai trace trust ledger"
    on public.shine_ai_trace_trust_ledger;
create policy "service role reads shine ai trace trust ledger"
    on public.shine_ai_trace_trust_ledger
    for select
    to service_role
    using (true);

revoke execute on function public.shine_ai_trace_trust_bootstrap_v1(integer,text,jsonb,text)
    from service_role;
revoke execute on function public.shine_ai_trace_trust_advance_v1(integer,text,integer,text,jsonb,text,text,text)
    from service_role;

create or replace function public.shine_ai_trace_trust_snapshot_v2()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    state_row public.shine_ai_trace_trust_state%rowtype;
    ledger_row public.shine_ai_trace_trust_ledger%rowtype;
    state_count bigint;
    ledger_count bigint;
begin
    select count(*) into state_count
    from public.shine_ai_trace_trust_state;

    select count(*) into ledger_count
    from public.shine_ai_trace_trust_ledger;

    if state_count = 0 and ledger_count = 0 then
        return jsonb_build_object(
            'status','unbootstrapped'
        );
    end if;

    if state_count <> 1 or ledger_count < 1 then
        return jsonb_build_object(
            'status','inconsistent',
            'reason_code','trust-storage-cardinality-mismatch',
            'state_rows',state_count,
            'ledger_rows',ledger_count
        );
    end if;

    select *
    into state_row
    from public.shine_ai_trace_trust_state
    where singleton = true;

    select *
    into ledger_row
    from public.shine_ai_trace_trust_ledger
    order by to_generation desc, id desc
    limit 1;

    if state_row.generation <> ledger_row.to_generation then
        return jsonb_build_object(
            'status','inconsistent',
            'reason_code','trust-generation-high-water-mismatch',
            'state_generation',state_row.generation,
            'ledger_generation',ledger_row.to_generation
        );
    end if;

    if state_row.keyset_sha256 <> ledger_row.to_keyset_sha256 then
        return jsonb_build_object(
            'status','inconsistent',
            'reason_code','trust-keyset-high-water-mismatch',
            'generation',state_row.generation
        );
    end if;

    return jsonb_build_object(
        'status','trusted',
        'generation',state_row.generation,
        'keyset_sha256',state_row.keyset_sha256,
        'trusted_keyset',state_row.trusted_keyset,
        'source',state_row.source,
        'authorization_key_id',state_row.authorization_key_id,
        'authorization_public_key_sha256',state_row.authorization_public_key_sha256,
        'accepted_at',state_row.accepted_at,
        'updated_at',state_row.updated_at,
        'ledger_rows',ledger_count
    );
end;
$$;

create or replace function public.shine_ai_trace_trust_bootstrap_v2(
    p_generation integer,
    p_keyset_sha256 text,
    p_trusted_keyset jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    snapshot jsonb;
begin
    perform pg_advisory_xact_lock(hashtext('shine-ai-trace-trust-v2'));

    if p_generation <> 1
       or p_keyset_sha256 !~ '^[a-f0-9]{64}$'
       or jsonb_typeof(p_trusted_keyset) <> 'object' then
        raise exception 'invalid trace trust genesis bootstrap';
    end if;

    snapshot := public.shine_ai_trace_trust_snapshot_v2();

    if snapshot->>'status' = 'trusted' then
        if (snapshot->>'generation')::integer = 1
           and snapshot->>'keyset_sha256' = p_keyset_sha256
           and snapshot->'trusted_keyset' = p_trusted_keyset then
            return jsonb_build_object(
                'status','already_trusted',
                'generation',1,
                'keyset_sha256',p_keyset_sha256
            );
        end if;
        raise exception 'trace trust genesis conflicts with persisted trust';
    end if;

    if snapshot->>'status' <> 'unbootstrapped' then
        raise exception 'trace trust storage inconsistent';
    end if;

    insert into public.shine_ai_trace_trust_state (
        singleton,
        generation,
        keyset_sha256,
        trusted_keyset,
        source,
        accepted_at,
        updated_at
    ) values (
        true,
        1,
        p_keyset_sha256,
        p_trusted_keyset,
        'genesis-pin',
        now(),
        now()
    );

    insert into public.shine_ai_trace_trust_ledger (
        from_generation,
        to_generation,
        from_keyset_sha256,
        to_keyset_sha256,
        acceptance_mode
    ) values (
        null,
        1,
        null,
        p_keyset_sha256,
        'genesis-pin'
    );

    return jsonb_build_object(
        'status','trusted',
        'generation',1,
        'keyset_sha256',p_keyset_sha256
    );
end;
$$;

create or replace function public.shine_ai_trace_trust_advance_v2(
    p_expected_generation integer,
    p_expected_keyset_sha256 text,
    p_next_generation integer,
    p_next_keyset_sha256 text,
    p_next_trusted_keyset jsonb,
    p_authorization_key_id text,
    p_authorization_public_key_sha256 text,
    p_certificate_sha256 text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    snapshot jsonb;
begin
    perform pg_advisory_xact_lock(hashtext('shine-ai-trace-trust-v2'));

    if p_expected_generation < 1
       or p_next_generation <> p_expected_generation + 1
       or p_expected_keyset_sha256 !~ '^[a-f0-9]{64}$'
       or p_next_keyset_sha256 !~ '^[a-f0-9]{64}$'
       or p_authorization_public_key_sha256 !~ '^[a-f0-9]{64}$'
       or p_certificate_sha256 !~ '^[a-f0-9]{64}$'
       or jsonb_typeof(p_next_trusted_keyset) <> 'object'
       or nullif(trim(p_authorization_key_id),'') is null then
        raise exception 'invalid trace trust transition';
    end if;

    snapshot := public.shine_ai_trace_trust_snapshot_v2();

    if snapshot->>'status' <> 'trusted' then
        raise exception 'trace trust storage inconsistent';
    end if;

    if (snapshot->>'generation')::integer <> p_expected_generation
       or snapshot->>'keyset_sha256' <> p_expected_keyset_sha256 then
        raise exception 'trace trust transition anti-rollback precondition mismatch';
    end if;

    update public.shine_ai_trace_trust_state
    set generation = p_next_generation,
        keyset_sha256 = p_next_keyset_sha256,
        trusted_keyset = p_next_trusted_keyset,
        source = 'signed-transition',
        authorization_key_id = p_authorization_key_id,
        authorization_public_key_sha256 = p_authorization_public_key_sha256,
        accepted_at = now(),
        updated_at = now()
    where singleton = true;

    insert into public.shine_ai_trace_trust_ledger (
        from_generation,
        to_generation,
        from_keyset_sha256,
        to_keyset_sha256,
        acceptance_mode,
        authorization_key_id,
        authorization_public_key_sha256,
        certificate_sha256
    ) values (
        p_expected_generation,
        p_next_generation,
        p_expected_keyset_sha256,
        p_next_keyset_sha256,
        'signed-transition',
        p_authorization_key_id,
        p_authorization_public_key_sha256,
        p_certificate_sha256
    );

    return jsonb_build_object(
        'status','advanced',
        'generation',p_next_generation,
        'keyset_sha256',p_next_keyset_sha256
    );
end;
$$;

revoke all on function public.shine_ai_trace_trust_snapshot_v2()
    from public, anon, authenticated;
revoke all on function public.shine_ai_trace_trust_bootstrap_v2(integer,text,jsonb)
    from public, anon, authenticated;
revoke all on function public.shine_ai_trace_trust_advance_v2(integer,text,integer,text,jsonb,text,text,text)
    from public, anon, authenticated;

grant execute on function public.shine_ai_trace_trust_snapshot_v2()
    to service_role;
grant execute on function public.shine_ai_trace_trust_bootstrap_v2(integer,text,jsonb)
    to service_role;
grant execute on function public.shine_ai_trace_trust_advance_v2(integer,text,integer,text,jsonb,text,text,text)
    to service_role;
