-- Layer 202: Foundation-side previous-quorum policy authorisation.
-- The Foundation witness keeps its HMAC secret in Foundation Vault and will
-- sign only a canonical N -> N+1 policy change after re-verifying its current
-- Project L trust-head witness/history.

create table if not exists foundation.project_l_policy_transition_authorization_events (
  event_id bigint generated always as identity primary key,
  witness_id text not null
    check (witness_id ~ '^[a-z0-9][a-z0-9._-]{0,63}$'),
  auth_key_id text not null
    check (auth_key_id ~ '^[a-z0-9][a-z0-9._-]{0,63}$'),
  from_generation integer not null check (from_generation between 1 and 1000000),
  to_generation integer not null check (to_generation=from_generation+1),
  from_policy_sha256 text not null check (from_policy_sha256 ~ '^[a-f0-9]{64}$'),
  to_policy_sha256 text not null check (to_policy_sha256 ~ '^[a-f0-9]{64}$'),
  auth_tag text not null check (auth_tag ~ '^[a-f0-9]{64}$'),
  client_id text not null,
  authorized_at timestamptz not null default now(),
  unique(witness_id,from_policy_sha256,to_policy_sha256,auth_key_id)
);

alter table foundation.project_l_policy_transition_authorization_events
  enable row level security;
revoke all on foundation.project_l_policy_transition_authorization_events
  from public,anon,authenticated,foundation_runtime,foundation_gateway,
       shine_defence_runtime;
revoke all on sequence foundation.project_l_policy_transition_authorization_events_event_id_seq
  from public,anon,authenticated,foundation_runtime,foundation_gateway,
       shine_defence_runtime;

create or replace function foundation.project_l_quorum_policy_digest_v1(
  p_policy jsonb
)
returns text
language plpgsql
security definer
set search_path=pg_catalog,foundation,extensions
as $$
declare
  v_generation integer;
  v_minimum integer;
  v_ids text[];
  v_ids_json text;
  v_previous text;
  v_claimed text;
  v_material text;
begin
  if p_policy is null
     or jsonb_typeof(p_policy)<>'object'
     or p_policy->>'policyVersion'<>'1'
     or p_policy->>'policyType'<>
       'decision_trace_trust_state_witness_quorum_policy' then
    raise exception 'invalid quorum policy';
  end if;

  begin
    v_generation := (p_policy->>'generation')::integer;
    v_minimum := (p_policy->>'minimumWitnesses')::integer;
  exception when others then
    raise exception 'invalid quorum policy';
  end;

  if v_generation<1 or v_generation>1000000
     or v_minimum<2 or v_minimum>4
     or jsonb_typeof(p_policy->'acceptedWitnessIds')<>'array'
     or jsonb_array_length(p_policy->'acceptedWitnessIds')<2
     or jsonb_array_length(p_policy->'acceptedWitnessIds')>4 then
    raise exception 'invalid quorum policy';
  end if;

  select array_agg(value order by ord),
         '[' || string_agg(to_json(value)::text,',' order by ord) || ']'
  into v_ids,v_ids_json
  from jsonb_array_elements_text(p_policy->'acceptedWitnessIds')
       with ordinality as x(value,ord);

  if v_ids is null
     or v_ids<>(
       select array_agg(value order by value)
       from unnest(v_ids) value
     )
     or cardinality(v_ids)<>(select count(distinct value) from unnest(v_ids) value)
     or exists(
       select 1 from unnest(v_ids) value
       where value !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
     )
     or v_minimum>cardinality(v_ids) then
    raise exception 'invalid quorum policy';
  end if;

  v_previous := p_policy->>'previousPolicySha256';
  if v_generation=1 then
    if p_policy->'previousPolicySha256' is distinct from 'null'::jsonb then
      raise exception 'invalid quorum policy';
    end if;
  elsif v_previous is null or v_previous !~ '^[a-f0-9]{64}$' then
    raise exception 'invalid quorum policy';
  end if;

  v_claimed := p_policy->>'policySha256';
  if v_claimed is null or v_claimed !~ '^[a-f0-9]{64}$' then
    raise exception 'invalid quorum policy';
  end if;

  v_material :=
    '{"policyVersion":1,"policyType":"decision_trace_trust_state_witness_quorum_policy",' ||
    '"generation":' || v_generation::text ||
    ',"minimumWitnesses":' || v_minimum::text ||
    ',"acceptedWitnessIds":' || v_ids_json ||
    ',"previousPolicySha256":' ||
      case when v_previous is null then 'null' else to_json(v_previous)::text end ||
    '}';

  if encode(extensions.digest(v_material,'sha256'),'hex')<>v_claimed then
    raise exception 'quorum policy digest mismatch';
  end if;
  return v_claimed;
end;
$$;

create or replace function foundation.project_l_policy_transition_authorize_v1(
  p_client_token text,
  p_previous_policy jsonb,
  p_next_policy jsonb
)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,foundation,vault,extensions
as $$
declare
  v_token_hash text;
  v_current_witness jsonb;
  v_from_sha text;
  v_to_sha text;
  v_from_generation integer;
  v_to_generation integer;
  v_from_minimum integer;
  v_to_minimum integer;
  v_from_ids text[];
  v_to_ids text[];
  v_secret text;
  v_auth_key_id text := 'foundation-witness-v1';
  v_material text;
  v_auth_input text;
  v_auth_tag text;
begin
  if p_client_token is null or length(p_client_token)<32 then
    return jsonb_build_object(
      'status','denied',
      'reasonCode','witness-client-unverified'
    );
  end if;

  v_token_hash := encode(extensions.digest(p_client_token,'sha256'),'hex');
  if not exists(
    select 1
    from foundation.effective_integration_client_credentials c
    where c.client_id='shine.companion'
      and c.effective_status='active'
      and c.token_hash=v_token_hash
      and (c.expires_at is null or c.expires_at>pg_catalog.now())
  ) then
    return jsonb_build_object(
      'status','denied',
      'reasonCode','witness-client-unverified'
    );
  end if;

  v_current_witness :=
    foundation.project_l_trace_witness_current_v1(
      p_client_token,
      'foundation-project-l'
    );
  if v_current_witness->>'status'<>'witnessed' then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','foundation-witness-current-unverified'
    );
  end if;

  begin
    v_from_sha := foundation.project_l_quorum_policy_digest_v1(p_previous_policy);
    v_to_sha := foundation.project_l_quorum_policy_digest_v1(p_next_policy);
    v_from_generation := (p_previous_policy->>'generation')::integer;
    v_to_generation := (p_next_policy->>'generation')::integer;
    v_from_minimum := (p_previous_policy->>'minimumWitnesses')::integer;
    v_to_minimum := (p_next_policy->>'minimumWitnesses')::integer;

    select array_agg(value order by ord)
    into v_from_ids
    from jsonb_array_elements_text(p_previous_policy->'acceptedWitnessIds')
         with ordinality as x(value,ord);
    select array_agg(value order by ord)
    into v_to_ids
    from jsonb_array_elements_text(p_next_policy->'acceptedWitnessIds')
         with ordinality as x(value,ord);
  exception when others then
    return jsonb_build_object(
      'status','invalid',
      'reasonCode','policy-transition-invalid'
    );
  end;

  if v_to_generation<>v_from_generation+1
     or p_next_policy->>'previousPolicySha256'<>v_from_sha
     or not ('foundation-project-l'=any(v_from_ids))
     or (v_to_minimum=v_from_minimum and v_to_ids=v_from_ids) then
    return jsonb_build_object(
      'status','invalid',
      'reasonCode','policy-transition-invalid'
    );
  end if;

  select decrypted_secret
  into v_secret
  from vault.decrypted_secrets
  where name='project_l_trace_witness_hmac_v1'
  order by created_at desc
  limit 1;

  if v_secret is null or length(v_secret)<32 then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','witness-signing-key-unavailable'
    );
  end if;

  v_material :=
    '{"authorizationVersion":1,' ||
    '"authorizationType":"decision_trace_trust_state_witness_quorum_policy_transition",' ||
    '"witnessId":"foundation-project-l",' ||
    '"fromGeneration":' || v_from_generation::text ||
    ',"toGeneration":' || v_to_generation::text ||
    ',"fromPolicySha256":"' || v_from_sha ||
    '","toPolicySha256":"' || v_to_sha || '"}';

  v_auth_input :=
    'shine-ai:decision-trace-trust-state-witness-quorum-policy-transition:v1' ||
    E'\n' || v_auth_key_id || E'\n' || v_material;

  v_auth_tag := encode(
    extensions.hmac(v_auth_input,v_secret,'sha256'),
    'hex'
  );

  insert into foundation.project_l_policy_transition_authorization_events(
    witness_id,auth_key_id,from_generation,to_generation,
    from_policy_sha256,to_policy_sha256,auth_tag,client_id,authorized_at
  ) values (
    'foundation-project-l',v_auth_key_id,v_from_generation,v_to_generation,
    v_from_sha,v_to_sha,v_auth_tag,'shine.companion',pg_catalog.now()
  )
  on conflict(witness_id,from_policy_sha256,to_policy_sha256,auth_key_id)
  do nothing;

  return jsonb_build_object(
    'status','authorized',
    'authorizationVersion',1,
    'authorizationType',
      'decision_trace_trust_state_witness_quorum_policy_transition',
    'authAlgorithm','HMAC-SHA-256',
    'witnessId','foundation-project-l',
    'authKeyId',v_auth_key_id,
    'fromGeneration',v_from_generation,
    'toGeneration',v_to_generation,
    'fromPolicySha256',v_from_sha,
    'toPolicySha256',v_to_sha,
    'authTag',v_auth_tag
  );
end;
$$;

create or replace function foundation.project_l_policy_transition_verify_v1(
  p_client_token text,
  p_previous_policy jsonb,
  p_next_policy jsonb,
  p_authorization jsonb
)
returns jsonb
language plpgsql
security definer
set search_path=pg_catalog,foundation,vault,extensions
as $$
declare
  v_expected jsonb;
begin
  v_expected := foundation.project_l_policy_transition_authorize_v1(
    p_client_token,p_previous_policy,p_next_policy
  );

  if v_expected->>'status'<>'authorized' then
    return v_expected;
  end if;

  if p_authorization is null
     or jsonb_typeof(p_authorization)<>'object'
     or p_authorization->>'authorizationVersion'<>v_expected->>'authorizationVersion'
     or p_authorization->>'authorizationType'<>v_expected->>'authorizationType'
     or p_authorization->>'authAlgorithm'<>v_expected->>'authAlgorithm'
     or p_authorization->>'witnessId'<>v_expected->>'witnessId'
     or p_authorization->>'authKeyId'<>v_expected->>'authKeyId'
     or p_authorization->>'fromGeneration'<>v_expected->>'fromGeneration'
     or p_authorization->>'toGeneration'<>v_expected->>'toGeneration'
     or p_authorization->>'fromPolicySha256'<>v_expected->>'fromPolicySha256'
     or p_authorization->>'toPolicySha256'<>v_expected->>'toPolicySha256'
     or p_authorization->>'authTag'<>v_expected->>'authTag' then
    return jsonb_build_object(
      'status','invalid',
      'reasonCode','policy-transition-authorization-invalid'
    );
  end if;

  return jsonb_build_object(
    'status','verified',
    'witnessId','foundation-project-l',
    'authKeyId',v_expected->>'authKeyId',
    'fromGeneration',(v_expected->>'fromGeneration')::integer,
    'toGeneration',(v_expected->>'toGeneration')::integer,
    'fromPolicySha256',v_expected->>'fromPolicySha256',
    'toPolicySha256',v_expected->>'toPolicySha256'
  );
end;
$$;

revoke all on function foundation.project_l_quorum_policy_digest_v1(jsonb)
  from public,anon,authenticated,foundation_runtime,foundation_gateway,
       shine_defence_runtime;
revoke all on function foundation.project_l_policy_transition_authorize_v1(
  text,jsonb,jsonb
) from public,anon,authenticated,foundation_runtime,shine_defence_runtime;
revoke all on function foundation.project_l_policy_transition_verify_v1(
  text,jsonb,jsonb,jsonb
) from public,anon,authenticated,foundation_runtime,shine_defence_runtime;

grant execute on function foundation.project_l_quorum_policy_digest_v1(jsonb)
  to foundation_gateway;
grant execute on function foundation.project_l_policy_transition_authorize_v1(
  text,jsonb,jsonb
) to foundation_gateway;
grant execute on function foundation.project_l_policy_transition_verify_v1(
  text,jsonb,jsonb,jsonb
) to foundation_gateway;
