-- Layer 206 follow-up: external witness roster high-water identity must
-- exclude local storage-authentication key metadata.
--
-- Generation, membership, threshold, predecessor policy, policy fingerprint,
-- and canonical trust-state SHA form the stable roster trust identity.
-- Rotating the local HMAC key ID/tag must not rewrite trust history or appear
-- as a roster rollback.

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

    select *
    into v_state
    from public.shine_ai_external_witness_roster_state
    where singleton = true;

    select *
    into v_ledger
    from public.shine_ai_external_witness_roster_ledger
    order by generation desc, id desc
    limit 1;

    if v_state.generation <> v_ledger.generation
       or v_state.minimum_witnesses <> v_ledger.minimum_witnesses
       or v_state.accepted_witness_ids <> v_ledger.accepted_witness_ids
       or v_state.previous_policy_sha256
            is distinct from v_ledger.previous_policy_sha256
       or v_state.policy_sha256 <> v_ledger.policy_sha256
       or v_state.state_sha256 <> v_ledger.state_sha256 then
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
