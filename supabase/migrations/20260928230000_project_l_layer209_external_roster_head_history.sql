-- Layer 209: contiguous external-witness-roster history and monotonic head source.
-- This fixes the generation-1-only snapshot cardinality assumption and exposes
-- a bounded service-role-only history used to derive Shine-AI Layer 161
-- checkpoint/head identities. No HMAC tags or transition authorization bodies
-- are returned.

create or replace function public.shine_ai_external_witness_roster_history_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_state public.shine_ai_external_witness_roster_state%rowtype;
  v_row public.shine_ai_external_witness_roster_ledger%rowtype;
  v_state_count bigint;
  v_ledger_count bigint;
  v_expected_generation integer := 1;
  v_previous_policy text := null;
  v_history jsonb := '[]'::jsonb;
begin
  select count(*) into v_state_count
  from public.shine_ai_external_witness_roster_state;

  select count(*) into v_ledger_count
  from public.shine_ai_external_witness_roster_ledger;

  if v_state_count=0 and v_ledger_count=0 then
    return jsonb_build_object('status','unbootstrapped');
  end if;

  if v_state_count<>1 or v_ledger_count<1 then
    return jsonb_build_object(
      'status','inconsistent',
      'reason_code','external-witness-roster-cardinality-mismatch'
    );
  end if;

  select * into v_state
  from public.shine_ai_external_witness_roster_state
  where singleton=true;

  if v_ledger_count<>v_state.generation then
    return jsonb_build_object(
      'status','inconsistent',
      'reason_code','external-witness-roster-generation-count-mismatch'
    );
  end if;

  for v_row in
    select *
    from public.shine_ai_external_witness_roster_ledger
    order by generation,id
  loop
    if v_row.generation<>v_expected_generation then
      return jsonb_build_object(
        'status','inconsistent',
        'reason_code','external-witness-roster-generation-gap'
      );
    end if;

    if v_expected_generation=1 then
      if v_row.previous_policy_sha256 is not null
         or v_row.acceptance_mode<>'genesis-pin' then
        return jsonb_build_object(
          'status','inconsistent',
          'reason_code','external-witness-roster-genesis-invalid'
        );
      end if;
    else
      if v_row.previous_policy_sha256 is distinct from v_previous_policy
         or v_row.acceptance_mode<>'previous-roster-quorum'
         or v_row.authorization_sha256 !~ '^[a-f0-9]{64}$'
         or cardinality(v_row.authorizing_witness_ids)<2 then
        return jsonb_build_object(
          'status','inconsistent',
          'reason_code','external-witness-roster-history-link-invalid'
        );
      end if;
    end if;

    if v_row.minimum_witnesses<2
       or v_row.minimum_witnesses>cardinality(v_row.accepted_witness_ids)
       or cardinality(v_row.accepted_witness_ids) not between 2 and 4
       or v_row.policy_sha256 !~ '^[a-f0-9]{64}$'
       or v_row.state_sha256 !~ '^[a-f0-9]{64}$' then
      return jsonb_build_object(
        'status','inconsistent',
        'reason_code','external-witness-roster-history-row-invalid'
      );
    end if;

    v_history := v_history || jsonb_build_array(
      jsonb_build_object(
        'generation',v_row.generation,
        'minimumWitnesses',v_row.minimum_witnesses,
        'acceptedWitnessIds',to_jsonb(v_row.accepted_witness_ids),
        'previousPolicySha256',v_row.previous_policy_sha256,
        'policySha256',v_row.policy_sha256,
        'stateSha256',v_row.state_sha256,
        'acceptanceMode',v_row.acceptance_mode,
        'authorizationSha256',v_row.authorization_sha256,
        'authorizingWitnessIds',to_jsonb(v_row.authorizing_witness_ids)
      )
    );

    v_previous_policy := v_row.policy_sha256;
    v_expected_generation := v_expected_generation+1;
  end loop;

  select * into v_row
  from public.shine_ai_external_witness_roster_ledger
  order by generation desc,id desc
  limit 1;

  if v_state.generation<>v_row.generation
     or v_state.minimum_witnesses<>v_row.minimum_witnesses
     or v_state.accepted_witness_ids<>v_row.accepted_witness_ids
     or v_state.previous_policy_sha256
          is distinct from v_row.previous_policy_sha256
     or v_state.policy_sha256<>v_row.policy_sha256
     or v_state.state_sha256<>v_row.state_sha256 then
    return jsonb_build_object(
      'status','inconsistent',
      'reason_code','external-witness-roster-high-water-mismatch'
    );
  end if;

  return jsonb_build_object(
    'status','trusted',
    'generation',v_state.generation,
    'policySha256',v_state.policy_sha256,
    'stateSha256',v_state.state_sha256,
    'history',v_history
  );
end;
$$;

create or replace function public.shine_ai_external_witness_roster_snapshot_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_state public.shine_ai_external_witness_roster_state%rowtype;
  v_history jsonb;
begin
  v_history := public.shine_ai_external_witness_roster_history_v1();

  if v_history->>'status'='unbootstrapped' then
    return v_history;
  end if;
  if v_history->>'status'<>'trusted' then
    return v_history;
  end if;

  select * into v_state
  from public.shine_ai_external_witness_roster_state
  where singleton=true;

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

revoke all on function
 public.shine_ai_external_witness_roster_history_v1()
 from public, anon, authenticated;
grant execute on function
 public.shine_ai_external_witness_roster_history_v1()
 to service_role;

revoke all on function
 public.shine_ai_external_witness_roster_snapshot_v1()
 from public, anon, authenticated;
grant execute on function
 public.shine_ai_external_witness_roster_snapshot_v1()
 to service_role;
