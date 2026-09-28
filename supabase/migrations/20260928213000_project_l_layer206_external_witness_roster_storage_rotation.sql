-- Layer 206: zero-reset storage authentication-key rotation for the
-- persisted external witness roster. Trusted roster state is immutable here:
-- only the storage authentication key ID/tag may change.

create or replace function public.shine_ai_external_witness_roster_rotate_storage_v1(
    p_expected_generation integer,
    p_expected_policy_sha256 text,
    p_expected_state_sha256 text,
    p_expected_storage_auth_key_id text,
    p_target_storage_auth_key_id text,
    p_target_storage_auth_tag text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    row_state public.shine_ai_external_witness_roster_state%rowtype;
begin
    perform pg_advisory_xact_lock(
        hashtext('shine-ai-external-witness-roster-storage-rotation-v1')
    );

    if p_expected_generation < 1
       or p_expected_policy_sha256 !~ '^[a-f0-9]{64}$'
       or p_expected_state_sha256 !~ '^[a-f0-9]{64}$'
       or p_expected_storage_auth_key_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
       or p_target_storage_auth_key_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
       or p_target_storage_auth_tag !~ '^[a-f0-9]{64}$' then
        raise exception 'invalid external witness roster storage rotation';
    end if;

    select *
    into row_state
    from public.shine_ai_external_witness_roster_state
    where singleton = true
    for update;

    if not found then
        raise exception 'external witness roster state missing';
    end if;

    if row_state.generation <> p_expected_generation
       or row_state.policy_sha256 <> p_expected_policy_sha256
       or row_state.state_sha256 <> p_expected_state_sha256 then
        raise exception 'external witness roster rotation state precondition mismatch';
    end if;

    if row_state.storage_auth_key_id = p_target_storage_auth_key_id then
        if row_state.storage_auth_tag = p_target_storage_auth_tag then
            return jsonb_build_object(
                'status','already_rotated',
                'generation',row_state.generation,
                'policy_sha256',row_state.policy_sha256,
                'state_sha256',row_state.state_sha256,
                'storage_auth_key_id',row_state.storage_auth_key_id
            );
        end if;
        raise exception 'external witness roster target key tag mismatch';
    end if;

    if row_state.storage_auth_key_id <> p_expected_storage_auth_key_id then
        raise exception 'external witness roster rotation source key mismatch';
    end if;

    update public.shine_ai_external_witness_roster_state
    set storage_auth_key_id = p_target_storage_auth_key_id,
        storage_auth_tag = p_target_storage_auth_tag,
        updated_at = now()
    where singleton = true
      and generation = p_expected_generation
      and policy_sha256 = p_expected_policy_sha256
      and state_sha256 = p_expected_state_sha256
      and storage_auth_key_id = p_expected_storage_auth_key_id;

    if not found then
        raise exception 'external witness roster storage rotation commit failed';
    end if;

    return jsonb_build_object(
        'status','rotated',
        'generation',p_expected_generation,
        'policy_sha256',p_expected_policy_sha256,
        'state_sha256',p_expected_state_sha256,
        'storage_auth_key_id',p_target_storage_auth_key_id
    );
end;
$$;

revoke all on function public.shine_ai_external_witness_roster_rotate_storage_v1(
    integer,text,text,text,text,text
) from public, anon, authenticated;

grant execute on function public.shine_ai_external_witness_roster_rotate_storage_v1(
    integer,text,text,text,text,text
) to service_role;
