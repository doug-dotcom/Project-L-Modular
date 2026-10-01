-- Independent Foundation witness for Shine-AI Project L health-attestation generation.

do $$
begin
  if not exists (
    select 1 from vault.decrypted_secrets
    where name='shine_ai_attestation_generation_witness_hmac_v1'
  ) then
    perform vault.create_secret(
      encode(extensions.gen_random_bytes(48),'base64'),
      'shine_ai_attestation_generation_witness_hmac_v1',
      'Foundation-only HMAC key for Shine-AI Project L health-attestation generation witness',
      null
    );
  end if;
end $$;

create table if not exists foundation.shine_ai_attestation_generation_witness_state (
  witness_id text primary key,
  generation integer not null check (generation between 1 and 1000000),
  key_id text not null check (key_id ~ '^[a-z0-9][a-z0-9._-]{0,79}$'),
  auth_key_id text not null,
  auth_tag text not null check (auth_tag ~ '^[a-f0-9]{64}$'),
  client_id text not null,
  witnessed_at timestamptz not null default now()
);

create table if not exists foundation.shine_ai_attestation_generation_witness_events (
  event_id bigint generated always as identity primary key,
  witness_id text not null,
  generation integer not null,
  key_id text not null,
  auth_key_id text not null,
  auth_tag text not null,
  client_id text not null,
  witnessed_at timestamptz not null default now(),
  unique (witness_id,generation)
);

alter table foundation.shine_ai_attestation_generation_witness_state enable row level security;
alter table foundation.shine_ai_attestation_generation_witness_events enable row level security;

drop policy if exists deny_all on foundation.shine_ai_attestation_generation_witness_state;
create policy deny_all
on foundation.shine_ai_attestation_generation_witness_state
for all
to public
using (false)
with check (false);

drop policy if exists deny_all on foundation.shine_ai_attestation_generation_witness_events;
create policy deny_all
on foundation.shine_ai_attestation_generation_witness_events
for all
to public
using (false)
with check (false);

revoke all on foundation.shine_ai_attestation_generation_witness_state
  from public, anon, authenticated, foundation_runtime, foundation_gateway,
       shine_defence_runtime, service_role;
revoke all on foundation.shine_ai_attestation_generation_witness_events
  from public, anon, authenticated, foundation_runtime, foundation_gateway,
       shine_defence_runtime, service_role;
revoke all on sequence foundation.shine_ai_attestation_generation_witness_events_event_id_seq
  from public, anon, authenticated, foundation_runtime, foundation_gateway,
       shine_defence_runtime, service_role;

create or replace function foundation.shine_ai_attestation_generation_witness_record_v1(
  p_client_token text,
  p_generation integer,
  p_key_id text,
  p_witness_id text default 'foundation-shine-ai-attestation-generation'
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, foundation, vault, extensions
as $$
declare
  v_token_hash text;
  v_current foundation.shine_ai_attestation_generation_witness_state%rowtype;
  v_secret text;
  v_auth_key_id text := 'foundation-shine-ai-attestation-generation-witness-v1';
  v_material text;
  v_tag text;
  v_current_tag text;
begin
  if p_client_token is null or length(p_client_token)<32
     or p_generation<1 or p_generation>1000000
     or p_key_id !~ '^[a-z0-9][a-z0-9._-]{0,79}$'
     or p_witness_id !~ '^[a-z0-9][a-z0-9._-]{0,79}$' then
    return jsonb_build_object('status','invalid','reasonCode','attestation-generation-witness-request-invalid');
  end if;

  v_token_hash := encode(extensions.digest(p_client_token,'sha256'),'hex');
  if not exists (
    select 1 from foundation.effective_integration_client_credentials c
    where c.client_id='shine.ai.runtime'
      and c.effective_status='active'
      and c.token_hash=v_token_hash
      and (c.expires_at is null or c.expires_at>pg_catalog.now())
  ) then
    return jsonb_build_object('status','denied','reasonCode','attestation-generation-witness-client-unverified');
  end if;

  select decrypted_secret into v_secret
  from vault.decrypted_secrets
  where name='shine_ai_attestation_generation_witness_hmac_v1'
  order by created_at desc limit 1;
  if v_secret is null or length(v_secret)<32 then
    return jsonb_build_object('status','unavailable','reasonCode','attestation-generation-witness-key-unavailable');
  end if;

  perform pg_advisory_xact_lock(hashtext('foundation-shine-ai-attestation-generation-v1'));
  select * into v_current
  from foundation.shine_ai_attestation_generation_witness_state
  where witness_id=p_witness_id for update;

  if found then
    v_material := '{"witnessVersion":1,"witnessId":"' || v_current.witness_id ||
      '","generation":' || v_current.generation::text ||
      ',"keyId":"' || v_current.key_id || '"}';
    v_current_tag := encode(
      extensions.hmac(
        'shine-ai:project-l-health-attestation-generation-witness:v1' || E'\n' ||
        v_current.auth_key_id || E'\n' || v_material,
        v_secret,'sha256'
      ),'hex'
    );
    if v_current_tag<>v_current.auth_tag then
      return jsonb_build_object('status','unavailable','reasonCode','attestation-generation-witness-integrity-failed');
    end if;

    if p_generation<v_current.generation then
      return jsonb_build_object('status','rejected','reasonCode','attestation-generation-witness-rollback','currentGeneration',v_current.generation);
    end if;
    if p_generation=v_current.generation then
      if p_key_id=v_current.key_id then
        return jsonb_build_object(
          'status','witnessed','replayed',true,'witnessVersion',1,
          'witnessType','project_l_health_attestation_generation_monotonic_witness',
          'authAlgorithm','HMAC-SHA-256','witnessId',v_current.witness_id,
          'authKeyId',v_current.auth_key_id,'clientId',v_current.client_id,'generation',v_current.generation,
          'keyId',v_current.key_id,'authTag',v_current.auth_tag,
          'independentRetention','foundation-supabase-vault-hmac',
          'witnessedAt',v_current.witnessed_at
        );
      end if;
      return jsonb_build_object('status','rejected','reasonCode','attestation-generation-witness-fork','currentGeneration',v_current.generation,'currentKeyId',v_current.key_id);
    end if;
    if p_generation<>v_current.generation+1 then
      return jsonb_build_object('status','rejected','reasonCode','attestation-generation-witness-skip','currentGeneration',v_current.generation);
    end if;
    if p_key_id=v_current.key_id then
      return jsonb_build_object('status','rejected','reasonCode','attestation-generation-witness-key-not-advanced');
    end if;
  end if;

  v_material := '{"witnessVersion":1,"witnessId":"' || p_witness_id ||
    '","generation":' || p_generation::text || ',"keyId":"' || p_key_id || '"}';
  v_tag := encode(
    extensions.hmac(
      'shine-ai:project-l-health-attestation-generation-witness:v1' || E'\n' ||
      v_auth_key_id || E'\n' || v_material,
      v_secret,'sha256'
    ),'hex'
  );

  insert into foundation.shine_ai_attestation_generation_witness_events(
    witness_id,generation,key_id,auth_key_id,auth_tag,client_id
  ) values (
    p_witness_id,p_generation,p_key_id,v_auth_key_id,v_tag,'shine.ai.runtime'
  );

  insert into foundation.shine_ai_attestation_generation_witness_state(
    witness_id,generation,key_id,auth_key_id,auth_tag,client_id
  ) values (
    p_witness_id,p_generation,p_key_id,v_auth_key_id,v_tag,'shine.ai.runtime'
  )
  on conflict (witness_id) do update
  set generation=excluded.generation,key_id=excluded.key_id,
      auth_key_id=excluded.auth_key_id,auth_tag=excluded.auth_tag,
      client_id=excluded.client_id,witnessed_at=now();

  return jsonb_build_object(
    'status','witnessed','replayed',false,'witnessVersion',1,
    'witnessType','project_l_health_attestation_generation_monotonic_witness',
    'authAlgorithm','HMAC-SHA-256','witnessId',p_witness_id,
    'authKeyId',v_auth_key_id,'clientId','shine.ai.runtime','generation',p_generation,'keyId',p_key_id,
    'authTag',v_tag,'independentRetention','foundation-supabase-vault-hmac',
    'witnessedAt',now()
  );
end;
$$;

create or replace function foundation.shine_ai_attestation_generation_witness_current_v1(
  p_client_token text,
  p_witness_id text default 'foundation-shine-ai-attestation-generation'
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, foundation, vault, extensions
as $$
declare
  v_token_hash text;
  v_state foundation.shine_ai_attestation_generation_witness_state%rowtype;
  v_secret text;
  v_material text;
  v_expected text;
begin
  if p_client_token is null or length(p_client_token)<32 then
    return jsonb_build_object('status','denied','reasonCode','attestation-generation-witness-client-unverified');
  end if;
  v_token_hash := encode(extensions.digest(p_client_token,'sha256'),'hex');
  if not exists (
    select 1 from foundation.effective_integration_client_credentials c
    where c.client_id='shine.ai.runtime'
      and c.effective_status='active'
      and c.token_hash=v_token_hash
      and (c.expires_at is null or c.expires_at>pg_catalog.now())
  ) then
    return jsonb_build_object('status','denied','reasonCode','attestation-generation-witness-client-unverified');
  end if;
  select * into v_state from foundation.shine_ai_attestation_generation_witness_state
  where witness_id=p_witness_id;
  if not found then return jsonb_build_object('status','empty','witnessId',p_witness_id); end if;
  select decrypted_secret into v_secret from vault.decrypted_secrets
  where name='shine_ai_attestation_generation_witness_hmac_v1'
  order by created_at desc limit 1;
  v_material := '{"witnessVersion":1,"witnessId":"' || v_state.witness_id ||
    '","generation":' || v_state.generation::text || ',"keyId":"' || v_state.key_id || '"}';
  v_expected := encode(
    extensions.hmac(
      'shine-ai:project-l-health-attestation-generation-witness:v1' || E'\n' ||
      v_state.auth_key_id || E'\n' || v_material,
      v_secret,'sha256'
    ),'hex'
  );
  if v_secret is null or v_expected<>v_state.auth_tag then
    return jsonb_build_object('status','unavailable','reasonCode','attestation-generation-witness-integrity-failed');
  end if;
  return jsonb_build_object(
    'status','witnessed','replayed',true,'witnessVersion',1,
    'witnessType','project_l_health_attestation_generation_monotonic_witness',
    'authAlgorithm','HMAC-SHA-256','witnessId',v_state.witness_id,
    'authKeyId',v_state.auth_key_id,'clientId',v_state.client_id,'generation',v_state.generation,
    'keyId',v_state.key_id,'authTag',v_state.auth_tag,
    'independentRetention','foundation-supabase-vault-hmac',
    'witnessedAt',v_state.witnessed_at
  );
end;
$$;

revoke all on function foundation.shine_ai_attestation_generation_witness_record_v1(text,integer,text,text)
from public, anon, authenticated, service_role, foundation_runtime, shine_defence_runtime;
revoke all on function foundation.shine_ai_attestation_generation_witness_current_v1(text,text)
from public, anon, authenticated, service_role, foundation_runtime, shine_defence_runtime;
grant execute on function foundation.shine_ai_attestation_generation_witness_record_v1(text,integer,text,text)
to foundation_gateway;
grant execute on function foundation.shine_ai_attestation_generation_witness_current_v1(text,text)
to foundation_gateway;
