-- Layer 191: durable Shine-AI decision-trace signing-keyset continuity.
-- Stores only public verification material and public fingerprints.
-- Service-role only; no user data or private signing material is stored.

create table if not exists public.shine_ai_trace_trust_state (
    singleton boolean primary key default true check (singleton),
    generation integer not null check (generation >= 1),
    keyset_sha256 text not null check (keyset_sha256 ~ '^[a-f0-9]{64}$'),
    trusted_keyset jsonb not null check (jsonb_typeof(trusted_keyset) = 'object'),
    source text not null check (source in ('genesis-pin','signed-transition','out-of-band-pin')),
    authorization_key_id text,
    authorization_public_key_sha256 text
        check (
            authorization_public_key_sha256 is null
            or authorization_public_key_sha256 ~ '^[a-f0-9]{64}$'
        ),
    accepted_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.shine_ai_trace_trust_ledger (
    id bigint generated always as identity primary key,
    from_generation integer check (from_generation is null or from_generation >= 1),
    to_generation integer not null check (to_generation >= 1),
    from_keyset_sha256 text
        check (
            from_keyset_sha256 is null
            or from_keyset_sha256 ~ '^[a-f0-9]{64}$'
        ),
    to_keyset_sha256 text not null
        check (to_keyset_sha256 ~ '^[a-f0-9]{64}$'),
    acceptance_mode text not null
        check (acceptance_mode in ('genesis-pin','signed-transition','out-of-band-pin')),
    authorization_key_id text,
    authorization_public_key_sha256 text
        check (
            authorization_public_key_sha256 is null
            or authorization_public_key_sha256 ~ '^[a-f0-9]{64}$'
        ),
    certificate_sha256 text
        check (
            certificate_sha256 is null
            or certificate_sha256 ~ '^[a-f0-9]{64}$'
        ),
    accepted_at timestamptz not null default now()
);

alter table public.shine_ai_trace_trust_state enable row level security;
alter table public.shine_ai_trace_trust_ledger enable row level security;

revoke all on public.shine_ai_trace_trust_state from anon, authenticated;
revoke all on public.shine_ai_trace_trust_ledger from anon, authenticated;

grant select, insert, update on public.shine_ai_trace_trust_state to service_role;
grant select, insert on public.shine_ai_trace_trust_ledger to service_role;
grant usage, select on sequence public.shine_ai_trace_trust_ledger_id_seq to service_role;

drop policy if exists "service role manages shine ai trace trust state"
    on public.shine_ai_trace_trust_state;
create policy "service role manages shine ai trace trust state"
    on public.shine_ai_trace_trust_state
    for all
    to service_role
    using (true)
    with check (true);

drop policy if exists "service role reads shine ai trace trust ledger"
    on public.shine_ai_trace_trust_ledger;
create policy "service role reads shine ai trace trust ledger"
    on public.shine_ai_trace_trust_ledger
    for select
    to service_role
    using (true);

drop policy if exists "service role appends shine ai trace trust ledger"
    on public.shine_ai_trace_trust_ledger;
create policy "service role appends shine ai trace trust ledger"
    on public.shine_ai_trace_trust_ledger
    for insert
    to service_role
    with check (true);

create or replace function public.shine_ai_trace_trust_bootstrap_v1(
    p_generation integer,
    p_keyset_sha256 text,
    p_trusted_keyset jsonb,
    p_source text default 'genesis-pin'
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    current_row public.shine_ai_trace_trust_state%rowtype;
begin
    if p_generation < 1
       or p_keyset_sha256 !~ '^[a-f0-9]{64}$'
       or jsonb_typeof(p_trusted_keyset) <> 'object'
       or p_source not in ('genesis-pin','out-of-band-pin') then
        raise exception 'invalid trace trust bootstrap';
    end if;

    select *
    into current_row
    from public.shine_ai_trace_trust_state
    where singleton = true
    for update;

    if found then
        if current_row.generation = p_generation
           and current_row.keyset_sha256 = p_keyset_sha256
           and current_row.trusted_keyset = p_trusted_keyset then
            return jsonb_build_object(
                'status','already_trusted',
                'generation',current_row.generation,
                'keyset_sha256',current_row.keyset_sha256
            );
        end if;
        raise exception 'trace trust bootstrap conflicts with existing trust state';
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
        p_generation,
        p_keyset_sha256,
        p_trusted_keyset,
        p_source,
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
        p_generation,
        null,
        p_keyset_sha256,
        p_source
    );

    return jsonb_build_object(
        'status','trusted',
        'generation',p_generation,
        'keyset_sha256',p_keyset_sha256
    );
end;
$$;

create or replace function public.shine_ai_trace_trust_advance_v1(
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
    current_row public.shine_ai_trace_trust_state%rowtype;
begin
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

    select *
    into current_row
    from public.shine_ai_trace_trust_state
    where singleton = true
    for update;

    if not found then
        raise exception 'trace trust state is not bootstrapped';
    end if;

    if current_row.generation <> p_expected_generation
       or current_row.keyset_sha256 <> p_expected_keyset_sha256 then
        raise exception 'trace trust transition precondition mismatch';
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

revoke all on function public.shine_ai_trace_trust_bootstrap_v1(integer,text,jsonb,text)
    from public, anon, authenticated;
revoke all on function public.shine_ai_trace_trust_advance_v1(integer,text,integer,text,jsonb,text,text,text)
    from public, anon, authenticated;

grant execute on function public.shine_ai_trace_trust_bootstrap_v1(integer,text,jsonb,text)
    to service_role;
grant execute on function public.shine_ai_trace_trust_advance_v1(integer,text,integer,text,jsonb,text,text,text)
    to service_role;
