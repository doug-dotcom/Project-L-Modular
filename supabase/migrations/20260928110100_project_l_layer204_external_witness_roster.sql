-- Layer 205: persisted authenticated external-witness roster trust.
-- Certified genesis roster: generation 1, 2-of-2
-- [foundation-project-l, redis-project-l].
-- No roster-advance RPC exists in this layer. Future membership changes must
-- add previous-external-quorum transition authorisation before they can persist.

create table if not exists public.shine_ai_external_witness_roster_state (
    singleton boolean primary key default true check (singleton),
    generation integer not null check (generation between 1 and 1000000),
    minimum_witnesses integer not null check (minimum_witnesses between 2 and 4),
    accepted_witness_ids text[] not null,
    previous_policy_sha256 text,
    policy_sha256 text not null check (policy_sha256 ~ '^[a-f0-9]{64}$'),
    source text not null check (source = 'genesis-pin'),
    state_sha256 text not null check (state_sha256 ~ '^[a-f0-9]{64}$'),
    storage_auth_key_id text not null
      check (storage_auth_key_id ~ '^[a-z0-9][a-z0-9._-]{0,63}$'),
    storage_auth_tag text not null check (storage_auth_tag ~ '^[a-f0-9]{64}$'),
    accepted_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (cardinality(accepted_witness_ids) between 2 and 4),
    check (minimum_witnesses <= cardinality(accepted_witness_ids)),
    check (
      previous_policy_sha256 is null
      or previous_policy_sha256 ~ '^[a-f0-9]{64}$'
    )
);

create table if not exists public.shine_ai_external_witness_roster_ledger (
    id bigint generated always as identity primary key,
    generation integer not null check (generation between 1 and 1000000),
    minimum_witnesses integer not null check (minimum_witnesses between 2 and 4),
    accepted_witness_ids text[] not null,
    previous_policy_sha256 text,
    policy_sha256 text not null check (policy_sha256 ~ '^[a-f0-9]{64}$'),
    state_sha256 text not null check (state_sha256 ~ '^[a-f0-9]{64}$'),
    storage_auth_key_id text not null
      check (storage_auth_key_id ~ '^[a-z0-9][a-z0-9._-]{0,63}$'),
    acceptance_mode text not null check (acceptance_mode = 'genesis-pin'),
    accepted_at timestamptz not null default now(),
    unique (generation),
    check (cardinality(accepted_witness_ids) between 2 and 4),
    check (minimum_witnesses <= cardinality(accepted_witness_ids)),
    check (
      previous_policy_sha256 is null
      or previous_policy_sha256 ~ '^[a-f0-9]{64}$'
    )
);

alter table public.shine_ai_external_witness_roster_state
  enable row level security;
alter table public.shine_ai_external_witness_roster_ledger
  enable row level security;

revoke all on public.shine_ai_external_witness_roster_state
  from public, anon, authenticated, service_role;
revoke all on public.shine_ai_external_witness_roster_ledger
  from public, anon, authenticated, service_role;
revoke all on sequence public.shine_ai_external_witness_roster_ledger_id_seq
  from public, anon, authenticated, service_role;

grant select on public.shine_ai_external_witness_roster_state to service_role;
grant select on public.shine_ai_external_witness_roster_ledger to service_role;
grant select on sequence public.shine_ai_external_witness_roster_ledger_id_seq
  to service_role;

drop policy if exists "service role reads external witness roster state"
  on public.shine_ai_external_witness_roster_state;
create policy "service role reads external witness roster state"
  on public.shine_ai_external_witness_roster_state
  for select to service_role using (true);

drop policy if exists "service role reads external witness roster ledger"
  on public.shine_ai_external_witness_roster_ledger;
create policy "service role reads external witness roster ledger"
  on public.shine_ai_external_witness_roster_ledger
  for select to service_role using (true);

create or replace function public.shine_ai_external_witness_roster_snapshot_v1()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_state public.shine_ai_external_witness_roster_state%rowtype;
    v_ledger public.shine_ai_external_witness_roster_ledger%rowtype;
    v_state_count bigint;
    v_ledger_count bigint;
begin
    select count(*) into v_state_count
    from public.shine_ai_external_witness_roster_state;
    select count(*) into v_ledger_count
    from public.shine_ai_external_witness_roster_ledger;

    if v_state_count = 0 and v_ledger_count = 0 then
        return jsonb_build_object('status','unbootstrapped');
    end if;
    if v_state_count <> 1 or v_ledger_count <> 1 then
        return jsonb_build_object(
            'status','inconsistent',
            'reason_code','external-witness-roster-cardinality-mismatch'
        );
    end if;

    select * into v_state
    from public.shine_ai_external_witness_roster_state
    where singleton=true;
    select * into v_ledger
    from public.shine_ai_external_witness_roster_ledger
    order by generation desc, id desc
    limit 1;

    if v_state.generation <> v_ledger.generation
       or v_state.minimum_witnesses <> v_ledger.minimum_witnesses
       or v_state.accepted_witness_ids <> v_ledger.accepted_witness_ids
       or v_state.previous_policy_sha256
            is distinct from v_ledger.previous_policy_sha256
       or v_state.policy_sha256 <> v_ledger.policy_sha256
       or v_state.state_sha256 <> v_ledger.state_sha256
       or v_state.storage_auth_key_id <> v_ledger.storage_auth_key_id then
        return jsonb_build_object(
            'status','inconsistent',
            'reason_code','external-witness-roster-high-water-mismatch'
        );
    end if;

    return jsonb_build_object(
        'status','trusted',
        'trust_state',jsonb_build_object(
            'trustStateVersion',1,
            'trustStateType',
              'decision_trace_trust_state_witness_quorum_policy_external_head_witness_quorum_policy',
            'generation',v_state.generation,
            'minimumWitnesses',v_state.minimum_witnesses,
            'acceptedWitnessIds',to_jsonb(v_state.accepted_witness_ids),
            'previousPolicySha256',v_state.previous_policy_sha256,
            'policySha256',v_state.policy_sha256
        ),
        'state_sha256',v_state.state_sha256,
        'storage_auth_key_id',v_state.storage_auth_key_id,
        'storage_auth_tag',v_state.storage_auth_tag
    );
end;
$$;

create or replace function public.shine_ai_external_witness_roster_bootstrap_v1(
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
    v_snapshot jsonb;
    v_ids text[] :=
      array['foundation-project-l','redis-project-l']::text[];
    v_policy_sha text :=
      'a5c456d49e47f1be3f2a7b7ed017328844484ba05c4e6ef3212412c6361156c4';
begin
    perform pg_advisory_xact_lock(
      hashtext('shine-ai-external-witness-roster-v1')
    );

    if p_state_sha256 !~ '^[a-f0-9]{64}$'
       or p_storage_auth_key_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
       or p_storage_auth_tag !~ '^[a-f0-9]{64}$' then
        raise exception 'external witness roster authentication invalid';
    end if;

    v_snapshot := public.shine_ai_external_witness_roster_snapshot_v1();
    if v_snapshot->>'status' = 'trusted' then
        if (v_snapshot->'trust_state'->>'generation')::integer = 1
           and (v_snapshot->'trust_state'->>'minimumWitnesses')::integer = 2
           and v_snapshot->'trust_state'->'acceptedWitnessIds' = to_jsonb(v_ids)
           and v_snapshot->'trust_state'->'previousPolicySha256' = 'null'::jsonb
           and v_snapshot->'trust_state'->>'policySha256' = v_policy_sha
           and v_snapshot->>'state_sha256' = p_state_sha256
           and v_snapshot->>'storage_auth_key_id' = p_storage_auth_key_id
           and v_snapshot->>'storage_auth_tag' = p_storage_auth_tag then
            return jsonb_build_object(
                'status','already_trusted',
                'trust_state',v_snapshot->'trust_state'
            );
        end if;
        raise exception 'external witness roster genesis conflicts with persisted trust';
    end if;

    if v_snapshot->>'status' <> 'unbootstrapped' then
        raise exception 'external witness roster storage inconsistent';
    end if;

    insert into public.shine_ai_external_witness_roster_state (
        singleton,
        generation,
        minimum_witnesses,
        accepted_witness_ids,
        previous_policy_sha256,
        policy_sha256,
        source,
        state_sha256,
        storage_auth_key_id,
        storage_auth_tag,
        accepted_at,
        updated_at
    ) values (
        true,
        1,
        2,
        v_ids,
        null,
        v_policy_sha,
        'genesis-pin',
        p_state_sha256,
        p_storage_auth_key_id,
        p_storage_auth_tag,
        now(),
        now()
    );

    insert into public.shine_ai_external_witness_roster_ledger (
        generation,
        minimum_witnesses,
        accepted_witness_ids,
        previous_policy_sha256,
        policy_sha256,
        state_sha256,
        storage_auth_key_id,
        acceptance_mode
    ) values (
        1,
        2,
        v_ids,
        null,
        v_policy_sha,
        p_state_sha256,
        p_storage_auth_key_id,
        'genesis-pin'
    );

    return jsonb_build_object(
        'status','trusted',
        'trust_state',jsonb_build_object(
            'trustStateVersion',1,
            'trustStateType',
              'decision_trace_trust_state_witness_quorum_policy_external_head_witness_quorum_policy',
            'generation',1,
            'minimumWitnesses',2,
            'acceptedWitnessIds',to_jsonb(v_ids),
            'previousPolicySha256',null,
            'policySha256',v_policy_sha
        )
    );
end;
$$;

revoke all on function public.shine_ai_external_witness_roster_snapshot_v1()
  from public, anon, authenticated;
revoke all on function public.shine_ai_external_witness_roster_bootstrap_v1(text,text,text)
  from public, anon, authenticated;

grant execute on function public.shine_ai_external_witness_roster_snapshot_v1()
  to service_role;
grant execute on function public.shine_ai_external_witness_roster_bootstrap_v1(text,text,text)
  to service_role;
