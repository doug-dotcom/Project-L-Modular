-- Layer 197: persisted 2-of-2 witness-quorum policy trust.
-- The genesis policy is pinned to:
--   minimum=2
--   witnesses=[foundation-project-l, project-l-redis]
-- Layer 197 intentionally exposes no policy-advance RPC. Membership changes
-- require a later previous-quorum-authorised transition contract.

create table if not exists public.shine_ai_witness_quorum_policy_state (
    singleton boolean primary key default true check (singleton),
    generation integer not null check (generation between 1 and 1000000),
    minimum_witnesses integer not null check (minimum_witnesses between 2 and 4),
    accepted_witness_ids text[] not null,
    previous_policy_sha256 text,
    policy_sha256 text not null check (policy_sha256 ~ '^[a-f0-9]{64}$'),
    source text not null check (source = 'genesis-pin'),
    accepted_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (cardinality(accepted_witness_ids) between 2 and 4),
    check (minimum_witnesses <= cardinality(accepted_witness_ids)),
    check (
      previous_policy_sha256 is null
      or previous_policy_sha256 ~ '^[a-f0-9]{64}$'
    )
);

create table if not exists public.shine_ai_witness_quorum_policy_ledger (
    id bigint generated always as identity primary key,
    generation integer not null check (generation between 1 and 1000000),
    minimum_witnesses integer not null check (minimum_witnesses between 2 and 4),
    accepted_witness_ids text[] not null,
    previous_policy_sha256 text,
    policy_sha256 text not null check (policy_sha256 ~ '^[a-f0-9]{64}$'),
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

alter table public.shine_ai_witness_quorum_policy_state
  enable row level security;
alter table public.shine_ai_witness_quorum_policy_ledger
  enable row level security;

revoke all on public.shine_ai_witness_quorum_policy_state
  from public, anon, authenticated, service_role;
revoke all on public.shine_ai_witness_quorum_policy_ledger
  from public, anon, authenticated, service_role;
revoke all on sequence public.shine_ai_witness_quorum_policy_ledger_id_seq
  from public, anon, authenticated, service_role;

grant select on public.shine_ai_witness_quorum_policy_state
  to service_role;
grant select on public.shine_ai_witness_quorum_policy_ledger
  to service_role;
grant select on sequence public.shine_ai_witness_quorum_policy_ledger_id_seq
  to service_role;

drop policy if exists "service role reads witness quorum policy state"
  on public.shine_ai_witness_quorum_policy_state;
create policy "service role reads witness quorum policy state"
  on public.shine_ai_witness_quorum_policy_state
  for select
  to service_role
  using (true);

drop policy if exists "service role reads witness quorum policy ledger"
  on public.shine_ai_witness_quorum_policy_ledger;
create policy "service role reads witness quorum policy ledger"
  on public.shine_ai_witness_quorum_policy_ledger
  for select
  to service_role
  using (true);

create or replace function public.shine_ai_witness_quorum_policy_snapshot_v1()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_state public.shine_ai_witness_quorum_policy_state%rowtype;
    v_ledger public.shine_ai_witness_quorum_policy_ledger%rowtype;
    v_state_count bigint;
    v_ledger_count bigint;
begin
    select count(*) into v_state_count
    from public.shine_ai_witness_quorum_policy_state;

    select count(*) into v_ledger_count
    from public.shine_ai_witness_quorum_policy_ledger;

    if v_state_count = 0 and v_ledger_count = 0 then
        return jsonb_build_object('status','unbootstrapped');
    end if;

    if v_state_count <> 1 or v_ledger_count <> 1 then
        return jsonb_build_object(
            'status','inconsistent',
            'reason_code','witness-quorum-policy-cardinality-mismatch'
        );
    end if;

    select *
    into v_state
    from public.shine_ai_witness_quorum_policy_state
    where singleton = true;

    select *
    into v_ledger
    from public.shine_ai_witness_quorum_policy_ledger
    order by generation desc, id desc
    limit 1;

    if v_state.generation <> v_ledger.generation
       or v_state.minimum_witnesses <> v_ledger.minimum_witnesses
       or v_state.accepted_witness_ids <> v_ledger.accepted_witness_ids
       or v_state.previous_policy_sha256 is distinct from v_ledger.previous_policy_sha256
       or v_state.policy_sha256 <> v_ledger.policy_sha256 then
        return jsonb_build_object(
            'status','inconsistent',
            'reason_code','witness-quorum-policy-high-water-mismatch'
        );
    end if;

    return jsonb_build_object(
        'status','trusted',
        'trust_state',jsonb_build_object(
            'trustStateVersion',1,
            'trustStateType','decision_trace_trust_state_witness_quorum_policy',
            'generation',v_state.generation,
            'minimumWitnesses',v_state.minimum_witnesses,
            'acceptedWitnessIds',to_jsonb(v_state.accepted_witness_ids),
            'previousPolicySha256',v_state.previous_policy_sha256,
            'policySha256',v_state.policy_sha256
        )
    );
end;
$$;

create or replace function public.shine_ai_witness_quorum_policy_bootstrap_v1()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_snapshot jsonb;
    v_ids text[] := array['foundation-project-l','project-l-redis']::text[];
    v_policy_sha text :=
      'aac7d1acaec5bf64d5f7d3fe535cbb48e99df0900eb91e8a8b44cbbfcbb5a92e';
begin
    perform pg_advisory_xact_lock(
      hashtext('shine-ai-witness-quorum-policy-v1')
    );

    v_snapshot := public.shine_ai_witness_quorum_policy_snapshot_v1();

    if v_snapshot->>'status' = 'trusted' then
        if (v_snapshot->'trust_state'->>'generation')::integer = 1
           and (v_snapshot->'trust_state'->>'minimumWitnesses')::integer = 2
           and v_snapshot->'trust_state'->'acceptedWitnessIds' =
               to_jsonb(v_ids)
           and v_snapshot->'trust_state'->'previousPolicySha256' = 'null'::jsonb
           and v_snapshot->'trust_state'->>'policySha256' = v_policy_sha then
            return jsonb_build_object(
                'status','already_trusted',
                'trust_state',v_snapshot->'trust_state'
            );
        end if;
        raise exception 'witness quorum genesis conflicts with persisted policy';
    end if;

    if v_snapshot->>'status' <> 'unbootstrapped' then
        raise exception 'witness quorum policy storage inconsistent';
    end if;

    insert into public.shine_ai_witness_quorum_policy_state (
        singleton,
        generation,
        minimum_witnesses,
        accepted_witness_ids,
        previous_policy_sha256,
        policy_sha256,
        source,
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
        now(),
        now()
    );

    insert into public.shine_ai_witness_quorum_policy_ledger (
        generation,
        minimum_witnesses,
        accepted_witness_ids,
        previous_policy_sha256,
        policy_sha256,
        acceptance_mode
    ) values (
        1,
        2,
        v_ids,
        null,
        v_policy_sha,
        'genesis-pin'
    );

    return jsonb_build_object(
        'status','trusted',
        'trust_state',jsonb_build_object(
            'trustStateVersion',1,
            'trustStateType','decision_trace_trust_state_witness_quorum_policy',
            'generation',1,
            'minimumWitnesses',2,
            'acceptedWitnessIds',to_jsonb(v_ids),
            'previousPolicySha256',null,
            'policySha256',v_policy_sha
        )
    );
end;
$$;

revoke all on function public.shine_ai_witness_quorum_policy_snapshot_v1()
  from public, anon, authenticated;
revoke all on function public.shine_ai_witness_quorum_policy_bootstrap_v1()
  from public, anon, authenticated;

grant execute on function public.shine_ai_witness_quorum_policy_snapshot_v1()
  to service_role;
grant execute on function public.shine_ai_witness_quorum_policy_bootstrap_v1()
  to service_role;
