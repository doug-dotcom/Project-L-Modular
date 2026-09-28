-- Layer 194: independent Foundation witness for Project L trust heads.
-- The witness secret stays in Foundation Vault. Project L authenticates using its
-- existing registered shine.companion integration-client token.

do $$
begin
  if not exists (
    select 1
    from vault.decrypted_secrets
    where name='project_l_trace_witness_hmac_v1'
  ) then
    perform vault.create_secret(
      encode(extensions.gen_random_bytes(48),'base64'),
      'project_l_trace_witness_hmac_v1',
      'Foundation-only HMAC key for Project L monotonic trust-head witnesses',
      null
    );
  end if;
end $$;

create table if not exists foundation.project_l_trace_witness_state (
  witness_id text primary key
    check (witness_id ~ '^[a-z0-9][a-z0-9._-]{0,63}$'),
  sequence bigint not null check (sequence between 1 and 10000000),
  head_sha256 text not null check (head_sha256 ~ '^[a-f0-9]{64}$'),
  generation integer not null check (generation between 1 and 1000000),
  keyset_sha256 text not null check (keyset_sha256 ~ '^[a-f0-9]{64}$'),
  state_sha256 text not null check (state_sha256 ~ '^[a-f0-9]{64}$'),
  auth_key_id text not null
    check (auth_key_id ~ '^[a-z0-9][a-z0-9._-]{0,63}$'),
  auth_tag text not null check (auth_tag ~ '^[a-f0-9]{64}$'),
  client_id text not null,
  witnessed_at timestamptz not null default now()
);

create table if not exists foundation.project_l_trace_witness_events (
  event_id bigint generated always as identity primary key,
  witness_id text not null,
  sequence bigint not null check (sequence between 1 and 10000000),
  head_sha256 text not null check (head_sha256 ~ '^[a-f0-9]{64}$'),
  generation integer not null check (generation between 1 and 1000000),
  keyset_sha256 text not null check (keyset_sha256 ~ '^[a-f0-9]{64}$'),
  state_sha256 text not null check (state_sha256 ~ '^[a-f0-9]{64}$'),
  auth_key_id text not null,
  auth_tag text not null check (auth_tag ~ '^[a-f0-9]{64}$'),
  client_id text not null,
  witnessed_at timestamptz not null default now(),
  unique (witness_id, sequence)
);

alter table foundation.project_l_trace_witness_state enable row level security;
alter table foundation.project_l_trace_witness_events enable row level security;

revoke all on foundation.project_l_trace_witness_state
  from public, anon, authenticated, foundation_runtime, foundation_gateway,
       shine_defence_runtime;
revoke all on foundation.project_l_trace_witness_events
  from public, anon, authenticated, foundation_runtime, foundation_gateway,
       shine_defence_runtime;
revoke all on sequence foundation.project_l_trace_witness_events_event_id_seq
  from public, anon, authenticated, foundation_runtime, foundation_gateway,
       shine_defence_runtime;

create or replace function foundation.project_l_trace_witness_current_v1(
  p_client_token text,
  p_witness_id text default 'foundation-project-l'
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, foundation, vault, extensions
as $$
declare
  v_token_hash text;
  v_state foundation.project_l_trace_witness_state%rowtype;
  v_event foundation.project_l_trace_witness_events%rowtype;
  v_secret text;
  v_material text;
  v_auth_input text;
  v_expected_tag text;
begin
  if p_client_token is null or length(p_client_token)<32
     or p_witness_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$' then
    return jsonb_build_object(
      'status','denied',
      'reasonCode','witness-client-unverified'
    );
  end if;

  v_token_hash := encode(extensions.digest(p_client_token,'sha256'),'hex');

  if not exists (
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

  select *
  into v_state
  from foundation.project_l_trace_witness_state s
  where s.witness_id=p_witness_id;

  if not found then
    return jsonb_build_object(
      'status','empty',
      'witnessId',p_witness_id
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
    '{"witnessVersion":1,"witnessType":"decision_trace_trust_state_monotonic_head_witness",' ||
    '"witnessId":"' || v_state.witness_id || '","headVersion":1,' ||
    '"sequence":' || v_state.sequence::text ||
    ',"headSha256":"' || v_state.head_sha256 ||
    '","generation":' || v_state.generation::text ||
    ',"keyset_sha256":"' || v_state.keyset_sha256 ||
    '","stateSha256":"' || v_state.state_sha256 || '"}';

  v_auth_input :=
    'shine-ai:decision-trace-trust-state-monotonic-head-witness:v1' ||
    E'\n' || v_state.auth_key_id || E'\n' || v_material;

  v_expected_tag := encode(
    extensions.hmac(v_auth_input,v_secret,'sha256'),
    'hex'
  );

  if v_expected_tag<>v_state.auth_tag then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','witness-auth-integrity-failed'
    );
  end if;

  select *
  into v_event
  from foundation.project_l_trace_witness_events e
  where e.witness_id=v_state.witness_id
    and e.sequence=v_state.sequence
  order by e.event_id desc
  limit 1;

  if not found
     or v_event.head_sha256 is distinct from v_state.head_sha256
     or v_event.generation is distinct from v_state.generation
     or v_event.keyset_sha256 is distinct from v_state.keyset_sha256
     or v_event.state_sha256 is distinct from v_state.state_sha256
     or v_event.auth_key_id is distinct from v_state.auth_key_id
     or v_event.auth_tag is distinct from v_state.auth_tag
     or v_event.client_id is distinct from v_state.client_id then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','witness-history-integrity-failed'
    );
  end if;

  return jsonb_build_object(
    'status','witnessed',
    'witnessVersion',1,
    'witnessType','decision_trace_trust_state_monotonic_head_witness',
    'authAlgorithm','HMAC-SHA-256',
    'witnessId',v_state.witness_id,
    'authKeyId',v_state.auth_key_id,
    'headVersion',1,
    'sequence',v_state.sequence,
    'headSha256',v_state.head_sha256,
    'generation',v_state.generation,
    'keyset_sha256',v_state.keyset_sha256,
    'stateSha256',v_state.state_sha256,
    'authTag',v_state.auth_tag,
    'witnessedAt',v_state.witnessed_at
  );
end;
$$;

create or replace function foundation.project_l_trace_witness_record_v1(
  p_client_token text,
  p_witness_id text,
  p_sequence bigint,
  p_head_sha256 text,
  p_generation integer,
  p_keyset_sha256 text,
  p_state_sha256 text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, foundation, vault, extensions
as $$
declare
  v_token_hash text;
  v_current foundation.project_l_trace_witness_state%rowtype;
  v_secret text;
  v_auth_key_id text := 'foundation-witness-v1';
  v_material text;
  v_auth_input text;
  v_auth_tag text;
begin
  if p_client_token is null or length(p_client_token)<32
     or p_witness_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
     or p_sequence<1 or p_sequence>10000000
     or p_head_sha256 !~ '^[a-f0-9]{64}$'
     or p_generation<1 or p_generation>1000000
     or p_keyset_sha256 !~ '^[a-f0-9]{64}$'
     or p_state_sha256 !~ '^[a-f0-9]{64}$' then
    return jsonb_build_object(
      'status','invalid',
      'reasonCode','witness-request-invalid'
    );
  end if;

  v_token_hash := encode(extensions.digest(p_client_token,'sha256'),'hex');

  if not exists (
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

  perform pg_advisory_xact_lock(hashtext('foundation-project-l-trace-witness-v1'));

  select *
  into v_current
  from foundation.project_l_trace_witness_state s
  where s.witness_id=p_witness_id
  for update;

  if found then
    if p_sequence<v_current.sequence then
      return jsonb_build_object(
        'status','rejected',
        'reasonCode','witness-sequence-rollback',
        'currentSequence',v_current.sequence
      );
    end if;

    if p_sequence=v_current.sequence then
      if p_head_sha256=v_current.head_sha256
         and p_generation=v_current.generation
         and p_keyset_sha256=v_current.keyset_sha256
         and p_state_sha256=v_current.state_sha256 then
        return jsonb_build_object(
          'status','witnessed',
          'replayed',true,
          'witnessVersion',1,
          'witnessType','decision_trace_trust_state_monotonic_head_witness',
          'authAlgorithm','HMAC-SHA-256',
          'witnessId',v_current.witness_id,
          'authKeyId',v_current.auth_key_id,
          'headVersion',1,
          'sequence',v_current.sequence,
          'headSha256',v_current.head_sha256,
          'generation',v_current.generation,
          'keyset_sha256',v_current.keyset_sha256,
          'stateSha256',v_current.state_sha256,
          'authTag',v_current.auth_tag,
          'witnessedAt',v_current.witnessed_at
        );
      end if;
      return jsonb_build_object(
        'status','rejected',
        'reasonCode','witness-sequence-equivocation',
        'currentSequence',v_current.sequence
      );
    end if;

    if p_sequence<>v_current.sequence+1 then
      return jsonb_build_object(
        'status','rejected',
        'reasonCode','witness-sequence-skip',
        'currentSequence',v_current.sequence
      );
    end if;

    if p_generation<v_current.generation
       or p_generation>v_current.generation+1 then
      return jsonb_build_object(
        'status','rejected',
        'reasonCode','witness-generation-invalid',
        'currentGeneration',v_current.generation
      );
    end if;

    if p_generation=v_current.generation
       and p_keyset_sha256<>v_current.keyset_sha256 then
      return jsonb_build_object(
        'status','rejected',
        'reasonCode','witness-keyset-equivocation'
      );
    end if;

    if p_generation=v_current.generation+1
       and p_keyset_sha256=v_current.keyset_sha256 then
      return jsonb_build_object(
        'status','rejected',
        'reasonCode','witness-generation-without-keyset-change'
      );
    end if;

    if p_state_sha256=v_current.state_sha256 then
      return jsonb_build_object(
        'status','rejected',
        'reasonCode','witness-state-not-advanced'
      );
    end if;
  else
    if p_sequence<>1 or p_generation<>1 then
      return jsonb_build_object(
        'status','rejected',
        'reasonCode','witness-genesis-invalid'
      );
    end if;
  end if;

  v_material :=
    '{"witnessVersion":1,"witnessType":"decision_trace_trust_state_monotonic_head_witness",' ||
    '"witnessId":"' || p_witness_id || '","headVersion":1,' ||
    '"sequence":' || p_sequence::text ||
    ',"headSha256":"' || p_head_sha256 ||
    '","generation":' || p_generation::text ||
    ',"keyset_sha256":"' || p_keyset_sha256 ||
    '","stateSha256":"' || p_state_sha256 || '"}';

  v_auth_input :=
    'shine-ai:decision-trace-trust-state-monotonic-head-witness:v1' ||
    E'\n' || v_auth_key_id || E'\n' || v_material;

  v_auth_tag := encode(
    extensions.hmac(v_auth_input,v_secret,'sha256'),
    'hex'
  );

  insert into foundation.project_l_trace_witness_events(
    witness_id,sequence,head_sha256,generation,keyset_sha256,state_sha256,
    auth_key_id,auth_tag,client_id,witnessed_at
  ) values (
    p_witness_id,p_sequence,p_head_sha256,p_generation,p_keyset_sha256,
    p_state_sha256,v_auth_key_id,v_auth_tag,'shine.companion',pg_catalog.now()
  );

  insert into foundation.project_l_trace_witness_state(
    witness_id,sequence,head_sha256,generation,keyset_sha256,state_sha256,
    auth_key_id,auth_tag,client_id,witnessed_at
  ) values (
    p_witness_id,p_sequence,p_head_sha256,p_generation,p_keyset_sha256,
    p_state_sha256,v_auth_key_id,v_auth_tag,'shine.companion',pg_catalog.now()
  )
  on conflict (witness_id) do update
  set sequence=excluded.sequence,
      head_sha256=excluded.head_sha256,
      generation=excluded.generation,
      keyset_sha256=excluded.keyset_sha256,
      state_sha256=excluded.state_sha256,
      auth_key_id=excluded.auth_key_id,
      auth_tag=excluded.auth_tag,
      client_id=excluded.client_id,
      witnessed_at=excluded.witnessed_at;

  return jsonb_build_object(
    'status','witnessed',
    'replayed',false,
    'witnessVersion',1,
    'witnessType','decision_trace_trust_state_monotonic_head_witness',
    'authAlgorithm','HMAC-SHA-256',
    'witnessId',p_witness_id,
    'authKeyId',v_auth_key_id,
    'headVersion',1,
    'sequence',p_sequence,
    'headSha256',p_head_sha256,
    'generation',p_generation,
    'keyset_sha256',p_keyset_sha256,
    'stateSha256',p_state_sha256,
    'authTag',v_auth_tag,
    'witnessedAt',pg_catalog.now()
  );
end;
$$;

revoke all on function foundation.project_l_trace_witness_current_v1(text,text)
  from public, anon, authenticated, foundation_runtime, shine_defence_runtime;
revoke all on function foundation.project_l_trace_witness_record_v1(text,text,bigint,text,integer,text,text)
  from public, anon, authenticated, foundation_runtime, shine_defence_runtime;
grant execute on function foundation.project_l_trace_witness_current_v1(text,text)
  to foundation_gateway;
grant execute on function foundation.project_l_trace_witness_record_v1(text,text,bigint,text,integer,text,text)
  to foundation_gateway;
