-- Layer 208: append-only external-witness roster checkpoint chain.
-- Stable chain identity excludes HMAC key IDs/tags.

create table if not exists public.shine_ai_external_witness_roster_chain (
    sequence integer primary key
        check (sequence >= 1 and sequence <= 1000000),
    generation integer not null unique
        check (generation >= 1 and generation <= 1000000),
    previous_checkpoint_sha256 text
        check (
            previous_checkpoint_sha256 is null
            or previous_checkpoint_sha256 ~ '^[a-f0-9]{64}$'
        ),
    previous_policy_sha256 text
        check (
            previous_policy_sha256 is null
            or previous_policy_sha256 ~ '^[a-f0-9]{64}$'
        ),
    policy_sha256 text not null
        check (policy_sha256 ~ '^[a-f0-9]{64}$'),
    state_sha256 text not null
        check (state_sha256 ~ '^[a-f0-9]{64}$'),
    checkpoint_sha256 text not null unique
        check (checkpoint_sha256 ~ '^[a-f0-9]{64}$'),
    auth_key_id text not null
        check (auth_key_id ~ '^[a-z0-9][a-z0-9._-]{0,63}$'),
    auth_tag text not null
        check (auth_tag ~ '^[a-f0-9]{64}$'),
    recorded_at timestamptz not null default now()
);

alter table public.shine_ai_external_witness_roster_chain
    enable row level security;

revoke all on public.shine_ai_external_witness_roster_chain
    from anon, authenticated;
revoke insert, update, delete, truncate, references, trigger
    on public.shine_ai_external_witness_roster_chain
    from service_role;
grant select on public.shine_ai_external_witness_roster_chain
    to service_role;

drop policy if exists "service role reads external witness roster chain"
    on public.shine_ai_external_witness_roster_chain;
create policy "service role reads external witness roster chain"
    on public.shine_ai_external_witness_roster_chain
    for select to service_role using (true);

create or replace function public.shine_ai_external_witness_roster_chain_snapshot_v1()
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
    v_count bigint;
    v_min_sequence integer;
    v_max_sequence integer;
    v_max_generation integer;
    v_roster jsonb;
begin
    select count(*), min(sequence), max(sequence), max(generation)
    into v_count, v_min_sequence, v_max_sequence, v_max_generation
    from public.shine_ai_external_witness_roster_chain;

    if v_count = 0 then
        return jsonb_build_object('status','empty','records','[]'::jsonb);
    end if;

    if v_min_sequence <> 1
       or v_max_sequence <> v_count
       or v_max_generation <> v_count then
        return jsonb_build_object(
            'status','inconsistent',
            'reason_code','external-witness-roster-chain-cardinality-mismatch'
        );
    end if;

    v_roster := public.shine_ai_external_witness_roster_snapshot_v1();
    if v_roster->>'status' <> 'trusted' then
        return jsonb_build_object(
            'status','inconsistent',
            'reason_code','external-witness-roster-chain-roster-unavailable'
        );
    end if;

    if v_max_generation >
       (v_roster->'trust_state'->>'generation')::integer then
        return jsonb_build_object(
            'status','inconsistent',
            'reason_code','external-witness-roster-chain-ahead-of-roster'
        );
    end if;

    return jsonb_build_object(
        'status','ok',
        'records',(
            select jsonb_agg(
                jsonb_build_object(
                    'chainVersion',1,
                    'chainType',
                      'decision_trace_trust_state_witness_quorum_policy_external_head_witness_quorum_checkpoint_chain',
                    'authAlgorithm','HMAC-SHA-256',
                    'authKeyId',auth_key_id,
                    'sequence',sequence,
                    'previousCheckpointSha256',previous_checkpoint_sha256,
                    'trustStateVersion',1,
                    'generation',generation,
                    'previousPolicySha256',previous_policy_sha256,
                    'policySha256',policy_sha256,
                    'stateSha256',state_sha256,
                    'checkpointSha256',checkpoint_sha256,
                    'authTag',auth_tag
                )
                order by sequence
            )
            from public.shine_ai_external_witness_roster_chain
        )
    );
end;
$$;

create or replace function public.shine_ai_external_witness_roster_chain_append_v1(
    p_sequence integer,
    p_previous_checkpoint_sha256 text,
    p_generation integer,
    p_previous_policy_sha256 text,
    p_policy_sha256 text,
    p_state_sha256 text,
    p_checkpoint_sha256 text,
    p_auth_key_id text,
    p_auth_tag text
)
returns jsonb
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
    v_roster jsonb;
    v_last public.shine_ai_external_witness_roster_chain%rowtype;
    v_existing public.shine_ai_external_witness_roster_chain%rowtype;
    v_material text;
    v_computed text;
begin
    perform pg_advisory_xact_lock(
        hashtext('shine-ai-external-witness-roster-chain-v1')
    );

    if p_sequence < 1 or p_sequence > 1000000
       or p_generation < 1 or p_generation > 1000000
       or p_policy_sha256 !~ '^[a-f0-9]{64}$'
       or p_state_sha256 !~ '^[a-f0-9]{64}$'
       or p_checkpoint_sha256 !~ '^[a-f0-9]{64}$'
       or p_auth_key_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
       or p_auth_tag !~ '^[a-f0-9]{64}$'
       or (
         p_previous_checkpoint_sha256 is not null
         and p_previous_checkpoint_sha256 !~ '^[a-f0-9]{64}$'
       )
       or (
         p_previous_policy_sha256 is not null
         and p_previous_policy_sha256 !~ '^[a-f0-9]{64}$'
       ) then
        raise exception 'invalid external witness roster chain record';
    end if;

    v_roster := public.shine_ai_external_witness_roster_snapshot_v1();
    if v_roster->>'status' <> 'trusted'
       or (v_roster->'trust_state'->>'generation')::integer <> p_generation
       or v_roster->'trust_state'->>'policySha256' <> p_policy_sha256
       or v_roster->>'state_sha256' <> p_state_sha256 then
        raise exception 'external witness roster chain current-state mismatch';
    end if;

    select * into v_existing
    from public.shine_ai_external_witness_roster_chain
    where sequence = p_sequence;

    if found then
        if v_existing.generation = p_generation
           and v_existing.previous_checkpoint_sha256
                is not distinct from p_previous_checkpoint_sha256
           and v_existing.previous_policy_sha256
                is not distinct from p_previous_policy_sha256
           and v_existing.policy_sha256 = p_policy_sha256
           and v_existing.state_sha256 = p_state_sha256
           and v_existing.checkpoint_sha256 = p_checkpoint_sha256
           and v_existing.auth_key_id = p_auth_key_id
           and v_existing.auth_tag = p_auth_tag then
            return jsonb_build_object(
                'status','already_present',
                'sequence',p_sequence,
                'generation',p_generation,
                'checkpoint_sha256',p_checkpoint_sha256
            );
        end if;
        raise exception 'external witness roster chain sequence fork';
    end if;

    select * into v_last
    from public.shine_ai_external_witness_roster_chain
    order by sequence desc
    limit 1;

    if not found then
        if p_sequence <> 1
           or p_generation <> 1
           or p_previous_checkpoint_sha256 is not null
           or p_previous_policy_sha256 is not null then
            raise exception 'external witness roster chain genesis invalid';
        end if;
    else
        if p_sequence <> v_last.sequence + 1
           or p_generation <> v_last.generation + 1
           or p_previous_checkpoint_sha256 <> v_last.checkpoint_sha256
           or p_previous_policy_sha256 <> v_last.policy_sha256 then
            raise exception 'external witness roster chain predecessor mismatch';
        end if;
    end if;

    v_material :=
      '{"chainVersion":1,"chainType":"decision_trace_trust_state_witness_quorum_policy_external_head_witness_quorum_checkpoint_chain"' ||
      ',"sequence":' || p_sequence::text ||
      ',"previousCheckpointSha256":' ||
        case when p_previous_checkpoint_sha256 is null
          then 'null'
          else to_json(p_previous_checkpoint_sha256)::text end ||
      ',"trustStateVersion":1' ||
      ',"generation":' || p_generation::text ||
      ',"previousPolicySha256":' ||
        case when p_previous_policy_sha256 is null
          then 'null'
          else to_json(p_previous_policy_sha256)::text end ||
      ',"policySha256":' || to_json(p_policy_sha256)::text ||
      ',"stateSha256":' || to_json(p_state_sha256)::text ||
      '}';

    v_computed := encode(extensions.digest(v_material,'sha256'),'hex');
    if v_computed <> p_checkpoint_sha256 then
        raise exception 'external witness roster chain checkpoint digest mismatch';
    end if;

    insert into public.shine_ai_external_witness_roster_chain (
        sequence,
        generation,
        previous_checkpoint_sha256,
        previous_policy_sha256,
        policy_sha256,
        state_sha256,
        checkpoint_sha256,
        auth_key_id,
        auth_tag
    ) values (
        p_sequence,
        p_generation,
        p_previous_checkpoint_sha256,
        p_previous_policy_sha256,
        p_policy_sha256,
        p_state_sha256,
        p_checkpoint_sha256,
        p_auth_key_id,
        p_auth_tag
    );

    return jsonb_build_object(
        'status','appended',
        'sequence',p_sequence,
        'generation',p_generation,
        'checkpoint_sha256',p_checkpoint_sha256
    );
end;
$$;

revoke all on function
  public.shine_ai_external_witness_roster_chain_snapshot_v1()
  from public, anon, authenticated;
revoke all on function
  public.shine_ai_external_witness_roster_chain_append_v1(
    integer,text,integer,text,text,text,text,text,text
  )
  from public, anon, authenticated;

grant execute on function
  public.shine_ai_external_witness_roster_chain_snapshot_v1()
  to service_role;
grant execute on function
  public.shine_ai_external_witness_roster_chain_append_v1(
    integer,text,integer,text,text,text,text,text,text
  )
  to service_role;
