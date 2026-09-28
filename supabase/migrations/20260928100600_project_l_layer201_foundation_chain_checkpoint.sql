-- Layer 201: Project-L durable high-water checkpoint for the accepted
-- Foundation witness-history chain.
--
-- This is intentionally stored in Project L's Supabase, independent of the
-- Foundation Supabase witness history. A Project-L-only Vault HMAC authenticates
-- every accepted checkpoint row. The state + append-only ledger reject rollback,
-- same-sequence forks, sequence gaps and broken predecessor links.

do $$
begin
  if not exists (
    select 1
    from vault.decrypted_secrets
    where name='project_l_foundation_chain_checkpoint_hmac_v1'
  ) then
    perform vault.create_secret(
      encode(extensions.gen_random_bytes(48),'base64'),
      'project_l_foundation_chain_checkpoint_hmac_v1',
      'Project L only HMAC key for accepted Foundation witness chain high-water',
      null
    );
  end if;
end $$;

create table if not exists public.shine_ai_foundation_chain_checkpoint_state (
    singleton boolean primary key default true check (singleton),
    checkpoint_version integer not null check (checkpoint_version=1),
    witness_id text not null check (witness_id='foundation-project-l'),
    chain_version integer not null check (chain_version=1),
    sequence bigint not null check (sequence between 1 and 10000000),
    previous_chain_tag text not null
      check (previous_chain_tag ~ '^[a-f0-9]{64}$'),
    chain_tag text not null
      check (chain_tag ~ '^[a-f0-9]{64}$'),
    auth_key_id text not null
      check (auth_key_id ~ '^[a-z0-9][a-z0-9._-]{0,63}$'),
    auth_tag text not null
      check (auth_tag ~ '^[a-f0-9]{64}$'),
    accepted_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.shine_ai_foundation_chain_checkpoint_ledger (
    id bigint generated always as identity primary key,
    checkpoint_version integer not null check (checkpoint_version=1),
    witness_id text not null check (witness_id='foundation-project-l'),
    chain_version integer not null check (chain_version=1),
    sequence bigint not null check (sequence between 1 and 10000000),
    previous_chain_tag text not null
      check (previous_chain_tag ~ '^[a-f0-9]{64}$'),
    chain_tag text not null
      check (chain_tag ~ '^[a-f0-9]{64}$'),
    auth_key_id text not null
      check (auth_key_id ~ '^[a-z0-9][a-z0-9._-]{0,63}$'),
    auth_tag text not null
      check (auth_tag ~ '^[a-f0-9]{64}$'),
    acceptance_mode text not null
      check (acceptance_mode in ('genesis','advanced')),
    accepted_at timestamptz not null default now(),
    unique (sequence)
);

alter table public.shine_ai_foundation_chain_checkpoint_state
  enable row level security;
alter table public.shine_ai_foundation_chain_checkpoint_ledger
  enable row level security;

revoke all on public.shine_ai_foundation_chain_checkpoint_state
  from public, anon, authenticated, service_role;
revoke all on public.shine_ai_foundation_chain_checkpoint_ledger
  from public, anon, authenticated, service_role;
revoke all on sequence
  public.shine_ai_foundation_chain_checkpoint_ledger_id_seq
  from public, anon, authenticated, service_role;

create or replace function public.shine_ai_foundation_chain_checkpoint_snapshot_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, vault, extensions
as $$
declare
    v_state public.shine_ai_foundation_chain_checkpoint_state%rowtype;
    v_event public.shine_ai_foundation_chain_checkpoint_ledger%rowtype;
    v_secret text;
    v_state_count bigint;
    v_ledger_count bigint;
    v_expected_sequence bigint := 1;
    v_expected_previous text := repeat('0',64);
    v_last_chain_tag text;
    v_material text;
    v_expected_auth_tag text;
begin
    select count(*)
    into v_state_count
    from public.shine_ai_foundation_chain_checkpoint_state;

    select count(*)
    into v_ledger_count
    from public.shine_ai_foundation_chain_checkpoint_ledger;

    if v_state_count=0 and v_ledger_count=0 then
        return jsonb_build_object('status','unbootstrapped');
    end if;

    if v_state_count<>1 or v_ledger_count<1 then
        return jsonb_build_object(
            'status','inconsistent',
            'reason_code','foundation-chain-checkpoint-cardinality-mismatch'
        );
    end if;

    select *
    into v_state
    from public.shine_ai_foundation_chain_checkpoint_state
    where singleton=true;

    if v_ledger_count<>v_state.sequence then
        return jsonb_build_object(
            'status','inconsistent',
            'reason_code','foundation-chain-checkpoint-ledger-count-mismatch'
        );
    end if;

    select decrypted_secret
    into v_secret
    from vault.decrypted_secrets
    where name='project_l_foundation_chain_checkpoint_hmac_v1'
    order by created_at desc
    limit 1;

    if v_secret is null or length(v_secret)<32 then
        return jsonb_build_object(
            'status','unavailable',
            'reason_code','foundation-chain-checkpoint-key-unavailable'
        );
    end if;

    for v_event in
        select *
        from public.shine_ai_foundation_chain_checkpoint_ledger
        order by sequence
    loop
        if v_event.sequence<>v_expected_sequence then
            return jsonb_build_object(
                'status','inconsistent',
                'reason_code','foundation-chain-checkpoint-sequence-gap',
                'failed_sequence',v_event.sequence
            );
        end if;

        if v_event.previous_chain_tag<>v_expected_previous then
            return jsonb_build_object(
                'status','inconsistent',
                'reason_code','foundation-chain-checkpoint-link-mismatch',
                'failed_sequence',v_event.sequence
            );
        end if;

        v_material :=
          '{"checkpointVersion":1,"checkpointType":"foundation_witness_chain_high_water",' ||
          '"witnessId":"' || v_event.witness_id ||
          '","chainVersion":' || v_event.chain_version::text ||
          ',"sequence":' || v_event.sequence::text ||
          ',"previousChainTag":"' || v_event.previous_chain_tag ||
          '","chainTag":"' || v_event.chain_tag || '"}';

        v_expected_auth_tag := encode(
          extensions.hmac(
            'shine:project-l:foundation-witness-chain-checkpoint:v1' ||
            E'\n' || v_event.auth_key_id || E'\n' || v_material,
            v_secret,
            'sha256'
          ),
          'hex'
        );

        if v_expected_auth_tag<>v_event.auth_tag then
            return jsonb_build_object(
                'status','inconsistent',
                'reason_code','foundation-chain-checkpoint-auth-failed',
                'failed_sequence',v_event.sequence
            );
        end if;

        v_expected_previous := v_event.chain_tag;
        v_last_chain_tag := v_event.chain_tag;
        v_expected_sequence := v_expected_sequence+1;
    end loop;

    if v_state.sequence<>v_expected_sequence-1
       or v_state.chain_tag<>v_last_chain_tag then
        return jsonb_build_object(
            'status','inconsistent',
            'reason_code','foundation-chain-checkpoint-high-water-mismatch'
        );
    end if;

    select *
    into v_event
    from public.shine_ai_foundation_chain_checkpoint_ledger
    where sequence=v_state.sequence;

    if not found
       or v_event.checkpoint_version<>v_state.checkpoint_version
       or v_event.witness_id<>v_state.witness_id
       or v_event.chain_version<>v_state.chain_version
       or v_event.previous_chain_tag<>v_state.previous_chain_tag
       or v_event.chain_tag<>v_state.chain_tag
       or v_event.auth_key_id<>v_state.auth_key_id
       or v_event.auth_tag<>v_state.auth_tag then
        return jsonb_build_object(
            'status','inconsistent',
            'reason_code','foundation-chain-checkpoint-state-ledger-mismatch'
        );
    end if;

    v_material :=
      '{"checkpointVersion":1,"checkpointType":"foundation_witness_chain_high_water",' ||
      '"witnessId":"' || v_state.witness_id ||
      '","chainVersion":' || v_state.chain_version::text ||
      ',"sequence":' || v_state.sequence::text ||
      ',"previousChainTag":"' || v_state.previous_chain_tag ||
      '","chainTag":"' || v_state.chain_tag || '"}';

    v_expected_auth_tag := encode(
      extensions.hmac(
        'shine:project-l:foundation-witness-chain-checkpoint:v1' ||
        E'\n' || v_state.auth_key_id || E'\n' || v_material,
        v_secret,
        'sha256'
      ),
      'hex'
    );

    if v_expected_auth_tag<>v_state.auth_tag then
        return jsonb_build_object(
            'status','inconsistent',
            'reason_code','foundation-chain-checkpoint-state-auth-failed'
        );
    end if;

    return jsonb_build_object(
        'status','trusted',
        'checkpoint',jsonb_build_object(
            'checkpointVersion',1,
            'checkpointType','foundation_witness_chain_high_water',
            'witnessId',v_state.witness_id,
            'chainVersion',v_state.chain_version,
            'sequence',v_state.sequence,
            'previousChainTag',v_state.previous_chain_tag,
            'chainTag',v_state.chain_tag,
            'authKeyId',v_state.auth_key_id,
            'storage','project-l-supabase-vault-hmac',
            'ledgerRows',v_ledger_count
        )
    );
end;
$$;

create or replace function public.shine_ai_foundation_chain_checkpoint_observe_v1(
    p_witness_id text,
    p_chain_version integer,
    p_sequence bigint,
    p_previous_chain_tag text,
    p_chain_tag text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, vault, extensions
as $$
declare
    v_snapshot jsonb;
    v_current jsonb;
    v_secret text;
    v_auth_key_id text := 'project-l-foundation-chain-checkpoint-v1';
    v_material text;
    v_auth_tag text;
    v_mode text;
begin
    if p_witness_id<>'foundation-project-l'
       or p_chain_version<>1
       or p_sequence<1 or p_sequence>10000000
       or p_previous_chain_tag !~ '^[a-f0-9]{64}$'
       or p_chain_tag !~ '^[a-f0-9]{64}$' then
        return jsonb_build_object(
            'status','invalid',
            'reason_code','foundation-chain-checkpoint-request-invalid'
        );
    end if;

    perform pg_advisory_xact_lock(
      hashtext('shine-ai-foundation-chain-checkpoint-v1')
    );

    v_snapshot :=
      public.shine_ai_foundation_chain_checkpoint_snapshot_v1();

    if v_snapshot->>'status'='unbootstrapped' then
        if p_sequence<>1
           or p_previous_chain_tag<>repeat('0',64) then
            return jsonb_build_object(
                'status','rejected',
                'reason_code','foundation-chain-checkpoint-genesis-invalid'
            );
        end if;
        v_mode := 'genesis';
    elsif v_snapshot->>'status'='trusted' then
        v_current := v_snapshot->'checkpoint';

        if p_sequence<(v_current->>'sequence')::bigint then
            return jsonb_build_object(
                'status','rejected',
                'reason_code','foundation-chain-checkpoint-rollback',
                'current_sequence',(v_current->>'sequence')::bigint
            );
        end if;

        if p_sequence=(v_current->>'sequence')::bigint then
            if p_chain_version=(v_current->>'chainVersion')::integer
               and p_previous_chain_tag=v_current->>'previousChainTag'
               and p_chain_tag=v_current->>'chainTag' then
                return jsonb_build_object(
                    'status','trusted',
                    'mode','existing',
                    'checkpoint',v_current
                );
            end if;
            return jsonb_build_object(
                'status','rejected',
                'reason_code','foundation-chain-checkpoint-equivocation',
                'current_sequence',(v_current->>'sequence')::bigint
            );
        end if;

        if p_sequence<>(v_current->>'sequence')::bigint+1 then
            return jsonb_build_object(
                'status','rejected',
                'reason_code','foundation-chain-checkpoint-sequence-gap',
                'current_sequence',(v_current->>'sequence')::bigint
            );
        end if;

        if p_previous_chain_tag<>v_current->>'chainTag' then
            return jsonb_build_object(
                'status','rejected',
                'reason_code','foundation-chain-checkpoint-predecessor-mismatch'
            );
        end if;

        v_mode := 'advanced';
    else
        return jsonb_build_object(
            'status','unavailable',
            'reason_code',coalesce(
              v_snapshot->>'reason_code',
              'foundation-chain-checkpoint-storage-invalid'
            )
        );
    end if;

    select decrypted_secret
    into v_secret
    from vault.decrypted_secrets
    where name='project_l_foundation_chain_checkpoint_hmac_v1'
    order by created_at desc
    limit 1;

    if v_secret is null or length(v_secret)<32 then
        return jsonb_build_object(
            'status','unavailable',
            'reason_code','foundation-chain-checkpoint-key-unavailable'
        );
    end if;

    v_material :=
      '{"checkpointVersion":1,"checkpointType":"foundation_witness_chain_high_water",' ||
      '"witnessId":"' || p_witness_id ||
      '","chainVersion":' || p_chain_version::text ||
      ',"sequence":' || p_sequence::text ||
      ',"previousChainTag":"' || p_previous_chain_tag ||
      '","chainTag":"' || p_chain_tag || '"}';

    v_auth_tag := encode(
      extensions.hmac(
        'shine:project-l:foundation-witness-chain-checkpoint:v1' ||
        E'\n' || v_auth_key_id || E'\n' || v_material,
        v_secret,
        'sha256'
      ),
      'hex'
    );

    insert into public.shine_ai_foundation_chain_checkpoint_ledger(
        checkpoint_version,
        witness_id,
        chain_version,
        sequence,
        previous_chain_tag,
        chain_tag,
        auth_key_id,
        auth_tag,
        acceptance_mode,
        accepted_at
    ) values (
        1,
        p_witness_id,
        p_chain_version,
        p_sequence,
        p_previous_chain_tag,
        p_chain_tag,
        v_auth_key_id,
        v_auth_tag,
        v_mode,
        now()
    );

    insert into public.shine_ai_foundation_chain_checkpoint_state(
        singleton,
        checkpoint_version,
        witness_id,
        chain_version,
        sequence,
        previous_chain_tag,
        chain_tag,
        auth_key_id,
        auth_tag,
        accepted_at,
        updated_at
    ) values (
        true,
        1,
        p_witness_id,
        p_chain_version,
        p_sequence,
        p_previous_chain_tag,
        p_chain_tag,
        v_auth_key_id,
        v_auth_tag,
        now(),
        now()
    )
    on conflict (singleton) do update
    set checkpoint_version=excluded.checkpoint_version,
        witness_id=excluded.witness_id,
        chain_version=excluded.chain_version,
        sequence=excluded.sequence,
        previous_chain_tag=excluded.previous_chain_tag,
        chain_tag=excluded.chain_tag,
        auth_key_id=excluded.auth_key_id,
        auth_tag=excluded.auth_tag,
        updated_at=excluded.updated_at;

    return jsonb_build_object(
        'status','trusted',
        'mode',v_mode,
        'checkpoint',jsonb_build_object(
            'checkpointVersion',1,
            'checkpointType','foundation_witness_chain_high_water',
            'witnessId',p_witness_id,
            'chainVersion',p_chain_version,
            'sequence',p_sequence,
            'previousChainTag',p_previous_chain_tag,
            'chainTag',p_chain_tag,
            'authKeyId',v_auth_key_id,
            'storage','project-l-supabase-vault-hmac'
        )
    );
end;
$$;

revoke all on function
  public.shine_ai_foundation_chain_checkpoint_snapshot_v1()
  from public, anon, authenticated;
revoke all on function
  public.shine_ai_foundation_chain_checkpoint_observe_v1(
    text,integer,bigint,text,text
  )
  from public, anon, authenticated;

grant execute on function
  public.shine_ai_foundation_chain_checkpoint_snapshot_v1()
  to service_role;
grant execute on function
  public.shine_ai_foundation_chain_checkpoint_observe_v1(
    text,integer,bigint,text,text
  )
  to service_role;
