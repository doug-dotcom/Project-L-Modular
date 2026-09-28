-- Layer 207: Foundation authorizes external witness-roster transitions
-- only when its current witness/history is healthy and Foundation belongs to
-- the previous accepted roster.

create or replace function foundation.project_l_external_roster_transition_authorize_v1(
  p_client_token text,
  p_previous_policy jsonb,
  p_next_policy jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, foundation, vault, extensions
as $$
declare
  v_current jsonb;
  v_secret text;
  v_key_id text := 'foundation-witness-v1';
  v_material jsonb;
  v_auth_tag text;
begin
  v_current := foundation.project_l_trace_witness_current_v1(
    p_client_token,
    'foundation-project-l'
  );
  if v_current->>'status'<>'witnessed' then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','foundation-roster-transition-witness-unverified'
    );
  end if;

  if coalesce(p_previous_policy->'acceptedWitnessIds','[]'::jsonb)
       @> '["foundation-project-l"]'::jsonb is not true
     or (p_next_policy->>'generation')::integer
        <> (p_previous_policy->>'generation')::integer+1
     or p_next_policy->>'previousPolicySha256'
        <> p_previous_policy->>'policySha256' then
    return jsonb_build_object(
      'status','invalid',
      'reasonCode','foundation-roster-transition-invalid'
    );
  end if;

  select decrypted_secret into v_secret
  from vault.decrypted_secrets
  where name='project_l_trace_witness_hmac_v1'
  order by created_at desc limit 1;
  if v_secret is null or length(v_secret)<32 then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','foundation-roster-transition-key-unavailable'
    );
  end if;

  v_material := jsonb_build_object(
    'authorizationVersion',1,
    'authorizationType',
      'decision_trace_trust_state_external_witness_roster_transition',
    'witnessId','foundation-project-l',
    'fromGeneration',(p_previous_policy->>'generation')::integer,
    'toGeneration',(p_next_policy->>'generation')::integer,
    'fromPolicySha256',p_previous_policy->>'policySha256',
    'toPolicySha256',p_next_policy->>'policySha256'
  );

  v_auth_tag := encode(
    extensions.hmac(
      'shine-ai:external-witness-roster-transition-authorization:v1' ||
      E'\n' || v_key_id || E'\n' || v_material::text,
      v_secret,'sha256'
    ),'hex'
  );

  return v_material || jsonb_build_object(
    'status','authorized',
    'authAlgorithm','HMAC-SHA-256',
    'authKeyId',v_key_id,
    'authTag',v_auth_tag
  );
end;
$$;

revoke all on function
 foundation.project_l_external_roster_transition_authorize_v1(text,jsonb,jsonb)
 from public, anon, authenticated, service_role, foundation_runtime,
      shine_defence_runtime;
grant execute on function
 foundation.project_l_external_roster_transition_authorize_v1(text,jsonb,jsonb)
 to foundation_gateway;
