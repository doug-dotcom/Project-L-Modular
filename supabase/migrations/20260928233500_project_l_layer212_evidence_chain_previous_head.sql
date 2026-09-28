-- Layer 212: expose the immediate predecessor of the verified
-- external-roster transition-evidence chain head so an independently retained
-- witness can prove monotonic head continuity across database restores.

create or replace function
 public.shine_ai_external_roster_transition_evidence_chain_verify_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, vault, extensions
as $$
declare
  v_secret text;
  v_row record;
  v_expected_generation integer := 2;
  v_previous_chain_tag text := repeat('0',64);
  v_previous_policy_sha256 text := null;
  v_evidence_material jsonb;
  v_evidence_sha256 text;
  v_chain_material jsonb;
  v_expected_chain_tag text;
  v_rows integer := 0;
  v_latest_generation integer := 1;
  v_latest_previous_chain_tag text := null;
  v_latest_chain_tag text := null;
  v_latest_evidence_sha256 text := null;
begin
  select decrypted_secret into v_secret
  from vault.decrypted_secrets
  where name='project_l_external_roster_transition_evidence_chain_hmac_v1'
  order by created_at desc
  limit 1;
  if v_secret is null or length(v_secret)<32 then
    return jsonb_build_object(
      'status','unavailable',
      'reason_code','external-roster-transition-evidence-chain-key-unavailable'
    );
  end if;

  for v_row in
    select *
    from public.shine_ai_external_roster_transition_evidence
    order by generation
  loop
    if v_row.generation<>v_expected_generation then
      return jsonb_build_object(
        'status','inconsistent',
        'reason_code','external-roster-transition-evidence-chain-generation-gap',
        'failedGeneration',v_row.generation
      );
    end if;
    if v_row.chain_version<>1
       or v_row.previous_chain_tag<>v_previous_chain_tag then
      return jsonb_build_object(
        'status','inconsistent',
        'reason_code','external-roster-transition-evidence-chain-link-mismatch',
        'failedGeneration',v_row.generation
      );
    end if;
    if v_row.generation>2
       and v_row.previous_policy_sha256<>v_previous_policy_sha256 then
      return jsonb_build_object(
        'status','inconsistent',
        'reason_code','external-roster-transition-evidence-chain-policy-link-mismatch',
        'failedGeneration',v_row.generation
      );
    end if;

    v_evidence_material := jsonb_build_object(
      'evidenceVersion',1,
      'generation',v_row.generation,
      'previousPolicySha256',v_row.previous_policy_sha256,
      'policySha256',v_row.policy_sha256,
      'authorizationSha256',v_row.authorization_sha256,
      'authorizingWitnessIds',to_jsonb(v_row.authorizing_witness_ids),
      'authorizations',v_row.authorizations
    );
    v_evidence_sha256 := encode(
      extensions.digest(v_evidence_material::text,'sha256'),
      'hex'
    );
    if v_evidence_sha256<>v_row.evidence_sha256 then
      return jsonb_build_object(
        'status','inconsistent',
        'reason_code','external-roster-transition-evidence-chain-evidence-digest-mismatch',
        'failedGeneration',v_row.generation
      );
    end if;

    v_chain_material := jsonb_build_object(
      'chainVersion',1,
      'generation',v_row.generation,
      'previousChainTag',v_previous_chain_tag,
      'evidenceSha256',v_evidence_sha256,
      'previousPolicySha256',v_row.previous_policy_sha256,
      'policySha256',v_row.policy_sha256,
      'authorizationSha256',v_row.authorization_sha256
    );
    v_expected_chain_tag := encode(
      extensions.hmac(
        'shine:project-l:external-roster-transition-evidence-chain:v1' ||
        E'\n' || v_row.chain_auth_key_id || E'\n' ||
        v_chain_material::text,
        v_secret,
        'sha256'
      ),
      'hex'
    );
    if v_expected_chain_tag<>v_row.chain_tag then
      return jsonb_build_object(
        'status','inconsistent',
        'reason_code','external-roster-transition-evidence-chain-auth-failed',
        'failedGeneration',v_row.generation
      );
    end if;

    v_rows := v_rows+1;
    v_latest_generation := v_row.generation;
    v_latest_previous_chain_tag := v_previous_chain_tag;
    v_latest_chain_tag := v_row.chain_tag;
    v_latest_evidence_sha256 := v_row.evidence_sha256;
    v_previous_chain_tag := v_row.chain_tag;
    v_previous_policy_sha256 := v_row.policy_sha256;
    v_expected_generation := v_expected_generation+1;
  end loop;

  if v_rows=0 then
    return jsonb_build_object(
      'status','empty',
      'chainVersion',1,
      'latestGeneration',1,
      'rows',0
    );
  end if;

  return jsonb_build_object(
    'status','verified',
    'chainVersion',1,
    'latestGeneration',v_latest_generation,
    'rows',v_rows,
    'latestPreviousChainTag',v_latest_previous_chain_tag,
    'latestChainTag',v_latest_chain_tag,
    'latestEvidenceSha256',v_latest_evidence_sha256
  );
end;
$$;

revoke all on function
 public.shine_ai_external_roster_transition_evidence_chain_verify_v1()
 from public, anon, authenticated;
grant execute on function
 public.shine_ai_external_roster_transition_evidence_chain_verify_v1()
 to service_role;
