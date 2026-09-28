-- Layer 197: keyed append-only history chain for Project L trust witnesses.
-- Every witness event is linked to its predecessor using a Foundation-only HMAC.
-- Full history verification recomputes both the original event authentication and
-- the keyed chain from genesis through the current state.

alter table foundation.project_l_trace_witness_events
  add column if not exists chain_version integer,
  add column if not exists previous_chain_tag text,
  add column if not exists chain_tag text;

alter table foundation.project_l_trace_witness_state
  add column if not exists chain_version integer,
  add column if not exists chain_tag text;

do $$
declare
  v_secret text;
  v_event record;
  v_previous_chain_tag text;
  v_auth_material text;
  v_expected_auth_tag text;
  v_chain_material text;
  v_chain_tag text;
begin
  select decrypted_secret
  into v_secret
  from vault.decrypted_secrets
  where name='project_l_trace_witness_hmac_v1'
  order by created_at desc
  limit 1;

  if v_secret is null or length(v_secret)<32 then
    raise exception 'witness-chain-signing-key-unavailable';
  end if;

  for v_event in
    select *
    from foundation.project_l_trace_witness_events
    order by witness_id, sequence
  loop
    if v_event.sequence=1 then
      v_previous_chain_tag := repeat('0',64);
    else
      select e.chain_tag
      into v_previous_chain_tag
      from foundation.project_l_trace_witness_events e
      where e.witness_id=v_event.witness_id
        and e.sequence=v_event.sequence-1;

      if not found or v_previous_chain_tag is null then
        raise exception 'witness-chain-backfill-gap';
      end if;
    end if;

    v_auth_material :=
      '{"witnessVersion":1,"witnessType":"decision_trace_trust_state_monotonic_head_witness",' ||
      '"witnessId":"' || v_event.witness_id || '","headVersion":1,' ||
      '"sequence":' || v_event.sequence::text ||
      ',"headSha256":"' || v_event.head_sha256 ||
      '","generation":' || v_event.generation::text ||
      ',"keyset_sha256":"' || v_event.keyset_sha256 ||
      '","stateSha256":"' || v_event.state_sha256 || '"}';

    v_expected_auth_tag := encode(
      extensions.hmac(
        'shine-ai:decision-trace-trust-state-monotonic-head-witness:v1' ||
        E'\n' || v_event.auth_key_id || E'\n' || v_auth_material,
        v_secret,
        'sha256'
      ),
      'hex'
    );

    if v_expected_auth_tag<>v_event.auth_tag
       or v_event.client_id<>'shine.companion' then
      raise exception 'witness-chain-backfill-auth-integrity-failed';
    end if;

    v_chain_material :=
      '{"chainVersion":1,"witnessId":"' || v_event.witness_id ||
      '","sequence":' || v_event.sequence::text ||
      ',"previousChainTag":"' || v_previous_chain_tag ||
      '","authKeyId":"' || v_event.auth_key_id ||
      '","authTag":"' || v_event.auth_tag ||
      '","headSha256":"' || v_event.head_sha256 ||
      '","generation":' || v_event.generation::text ||
      ',"keyset_sha256":"' || v_event.keyset_sha256 ||
      '","stateSha256":"' || v_event.state_sha256 ||
      '","clientId":"' || v_event.client_id || '"}';

    v_chain_tag := encode(
      extensions.hmac(
        'shine-ai:decision-trace-trust-state-witness-chain:v1' ||
        E'\n' || v_chain_material,
        v_secret,
        'sha256'
      ),
      'hex'
    );

    update foundation.project_l_trace_witness_events
    set chain_version=1,
        previous_chain_tag=v_previous_chain_tag,
        chain_tag=v_chain_tag
    where event_id=v_event.event_id;
  end loop;

  if exists (
    select 1
    from foundation.project_l_trace_witness_state s
    left join foundation.project_l_trace_witness_events e
      on e.witness_id=s.witness_id
     and e.sequence=s.sequence
    where e.event_id is null
       or e.head_sha256 is distinct from s.head_sha256
       or e.generation is distinct from s.generation
       or e.keyset_sha256 is distinct from s.keyset_sha256
       or e.state_sha256 is distinct from s.state_sha256
       or e.auth_key_id is distinct from s.auth_key_id
       or e.auth_tag is distinct from s.auth_tag
       or e.client_id is distinct from s.client_id
       or e.chain_tag is null
  ) then
    raise exception 'witness-chain-backfill-state-integrity-failed';
  end if;

  update foundation.project_l_trace_witness_state s
  set chain_version=1,
      chain_tag=e.chain_tag
  from foundation.project_l_trace_witness_events e
  where e.witness_id=s.witness_id
    and e.sequence=s.sequence;
end;
$$;

alter table foundation.project_l_trace_witness_events
  alter column chain_version set not null,
  alter column previous_chain_tag set not null,
  alter column chain_tag set not null;

alter table foundation.project_l_trace_witness_state
  alter column chain_version set not null,
  alter column chain_tag set not null;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname='project_l_trace_witness_events_chain_version_check'
      and conrelid='foundation.project_l_trace_witness_events'::regclass
  ) then
    alter table foundation.project_l_trace_witness_events
      add constraint project_l_trace_witness_events_chain_version_check
      check (chain_version=1);
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname='project_l_trace_witness_events_previous_chain_tag_check'
      and conrelid='foundation.project_l_trace_witness_events'::regclass
  ) then
    alter table foundation.project_l_trace_witness_events
      add constraint project_l_trace_witness_events_previous_chain_tag_check
      check (previous_chain_tag ~ '^[a-f0-9]{64}$');
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname='project_l_trace_witness_events_chain_tag_check'
      and conrelid='foundation.project_l_trace_witness_events'::regclass
  ) then
    alter table foundation.project_l_trace_witness_events
      add constraint project_l_trace_witness_events_chain_tag_check
      check (chain_tag ~ '^[a-f0-9]{64}$');
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname='project_l_trace_witness_state_chain_version_check'
      and conrelid='foundation.project_l_trace_witness_state'::regclass
  ) then
    alter table foundation.project_l_trace_witness_state
      add constraint project_l_trace_witness_state_chain_version_check
      check (chain_version=1);
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname='project_l_trace_witness_state_chain_tag_check'
      and conrelid='foundation.project_l_trace_witness_state'::regclass
  ) then
    alter table foundation.project_l_trace_witness_state
      add constraint project_l_trace_witness_state_chain_tag_check
      check (chain_tag ~ '^[a-f0-9]{64}$');
  end if;
end;
$$;

create or replace function foundation.project_l_trace_witness_verify_history_v1(
  p_witness_id text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, foundation, vault, extensions
as $$
declare
  v_state foundation.project_l_trace_witness_state%rowtype;
  v_event foundation.project_l_trace_witness_events%rowtype;
  v_secret text;
  v_expected_sequence bigint := 1;
  v_previous_chain_tag text := repeat('0',64);
  v_auth_material text;
  v_expected_auth_tag text;
  v_chain_material text;
  v_expected_chain_tag text;
  v_last_sequence bigint := 0;
  v_last_head_sha256 text;
  v_last_generation integer;
  v_last_keyset_sha256 text;
  v_last_state_sha256 text;
  v_last_auth_key_id text;
  v_last_auth_tag text;
  v_last_client_id text;
  v_last_chain_tag text;
begin
  if p_witness_id is null
     or p_witness_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$' then
    return jsonb_build_object(
      'status','invalid',
      'reasonCode','witness-history-request-invalid'
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
      'reasonCode','witness-chain-signing-key-unavailable'
    );
  end if;

  for v_event in
    select *
    from foundation.project_l_trace_witness_events e
    where e.witness_id=p_witness_id
    order by e.sequence
  loop
    if v_event.sequence<>v_expected_sequence then
      return jsonb_build_object(
        'status','unavailable',
        'reasonCode','witness-chain-sequence-gap'
      );
    end if;

    v_auth_material :=
      '{"witnessVersion":1,"witnessType":"decision_trace_trust_state_monotonic_head_witness",' ||
      '"witnessId":"' || v_event.witness_id || '","headVersion":1,' ||
      '"sequence":' || v_event.sequence::text ||
      ',"headSha256":"' || v_event.head_sha256 ||
      '","generation":' || v_event.generation::text ||
      ',"keyset_sha256":"' || v_event.keyset_sha256 ||
      '","stateSha256":"' || v_event.state_sha256 || '"}';

    v_expected_auth_tag := encode(
      extensions.hmac(
        'shine-ai:decision-trace-trust-state-monotonic-head-witness:v1' ||
        E'\n' || v_event.auth_key_id || E'\n' || v_auth_material,
        v_secret,
        'sha256'
      ),
      'hex'
    );

    if v_expected_auth_tag<>v_event.auth_tag
       or v_event.client_id<>'shine.companion' then
      return jsonb_build_object(
        'status','unavailable',
        'reasonCode','witness-chain-event-auth-failed',
        'failedSequence',v_event.sequence
      );
    end if;

    if v_event.chain_version<>1
       or v_event.previous_chain_tag<>v_previous_chain_tag then
      return jsonb_build_object(
        'status','unavailable',
        'reasonCode','witness-chain-link-failed',
        'failedSequence',v_event.sequence
      );
    end if;

    v_chain_material :=
      '{"chainVersion":1,"witnessId":"' || v_event.witness_id ||
      '","sequence":' || v_event.sequence::text ||
      ',"previousChainTag":"' || v_previous_chain_tag ||
      '","authKeyId":"' || v_event.auth_key_id ||
      '","authTag":"' || v_event.auth_tag ||
      '","headSha256":"' || v_event.head_sha256 ||
      '","generation":' || v_event.generation::text ||
      ',"keyset_sha256":"' || v_event.keyset_sha256 ||
      '","stateSha256":"' || v_event.state_sha256 ||
      '","clientId":"' || v_event.client_id || '"}';

    v_expected_chain_tag := encode(
      extensions.hmac(
        'shine-ai:decision-trace-trust-state-witness-chain:v1' ||
        E'\n' || v_chain_material,
        v_secret,
        'sha256'
      ),
      'hex'
    );

    if v_expected_chain_tag<>v_event.chain_tag then
      return jsonb_build_object(
        'status','unavailable',
        'reasonCode','witness-chain-auth-failed',
        'failedSequence',v_event.sequence
      );
    end if;

    v_previous_chain_tag := v_event.chain_tag;
    v_last_sequence := v_event.sequence;
    v_last_head_sha256 := v_event.head_sha256;
    v_last_generation := v_event.generation;
    v_last_keyset_sha256 := v_event.keyset_sha256;
    v_last_state_sha256 := v_event.state_sha256;
    v_last_auth_key_id := v_event.auth_key_id;
    v_last_auth_tag := v_event.auth_tag;
    v_last_client_id := v_event.client_id;
    v_last_chain_tag := v_event.chain_tag;
    v_expected_sequence := v_expected_sequence+1;
  end loop;

  if v_last_sequence<>v_state.sequence
     or v_state.chain_version<>1
     or v_last_head_sha256 is distinct from v_state.head_sha256
     or v_last_generation is distinct from v_state.generation
     or v_last_keyset_sha256 is distinct from v_state.keyset_sha256
     or v_last_state_sha256 is distinct from v_state.state_sha256
     or v_last_auth_key_id is distinct from v_state.auth_key_id
     or v_last_auth_tag is distinct from v_state.auth_tag
     or v_last_client_id is distinct from v_state.client_id
     or v_last_chain_tag is distinct from v_state.chain_tag then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','witness-chain-head-mismatch'
    );
  end if;

  return jsonb_build_object(
    'status','verified',
    'witnessId',p_witness_id,
    'chainVersion',1,
    'sequence',v_state.sequence,
    'chainTag',v_state.chain_tag
  );
end;
$$;

revoke all on function foundation.project_l_trace_witness_verify_history_v1(text)
  from public, anon, authenticated, service_role, foundation_runtime,
       foundation_gateway, shine_defence_runtime;

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
  v_history jsonb;
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
     or v_event.client_id is distinct from v_state.client_id
     or v_event.chain_version is distinct from v_state.chain_version
     or v_event.chain_tag is distinct from v_state.chain_tag then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','witness-history-integrity-failed'
    );
  end if;

  v_history :=
    foundation.project_l_trace_witness_verify_history_v1(
      p_witness_id
    );
  if coalesce(v_history->>'status','')<>'verified' then
    return v_history;
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
    'chainVersion',v_state.chain_version,
    'previousChainTag',v_event.previous_chain_tag,
    'chainTag',v_state.chain_tag,
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
  v_current_event foundation.project_l_trace_witness_events%rowtype;
  v_secret text;
  v_auth_key_id text := 'foundation-witness-v1';
  v_material text;
  v_auth_input text;
  v_auth_tag text;
  v_current_material text;
  v_current_auth_input text;
  v_current_expected_tag text;
  v_history jsonb;
  v_previous_chain_tag text;
  v_chain_material text;
  v_chain_tag text;
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
    v_current_material :=
      '{"witnessVersion":1,"witnessType":"decision_trace_trust_state_monotonic_head_witness",' ||
      '"witnessId":"' || v_current.witness_id || '","headVersion":1,' ||
      '"sequence":' || v_current.sequence::text ||
      ',"headSha256":"' || v_current.head_sha256 ||
      '","generation":' || v_current.generation::text ||
      ',"keyset_sha256":"' || v_current.keyset_sha256 ||
      '","stateSha256":"' || v_current.state_sha256 || '"}';

    v_current_auth_input :=
      'shine-ai:decision-trace-trust-state-monotonic-head-witness:v1' ||
      E'\n' || v_current.auth_key_id || E'\n' || v_current_material;

    v_current_expected_tag := encode(
      extensions.hmac(v_current_auth_input,v_secret,'sha256'),
      'hex'
    );

    if v_current_expected_tag<>v_current.auth_tag then
      return jsonb_build_object(
        'status','unavailable',
        'reasonCode','witness-current-auth-integrity-failed'
      );
    end if;

    select *
    into v_current_event
    from foundation.project_l_trace_witness_events e
    where e.witness_id=v_current.witness_id
      and e.sequence=v_current.sequence
    order by e.event_id desc
    limit 1;

    if not found
       or v_current.client_id<>'shine.companion'
       or v_current_event.head_sha256 is distinct from v_current.head_sha256
       or v_current_event.generation is distinct from v_current.generation
       or v_current_event.keyset_sha256 is distinct from v_current.keyset_sha256
       or v_current_event.state_sha256 is distinct from v_current.state_sha256
       or v_current_event.auth_key_id is distinct from v_current.auth_key_id
       or v_current_event.auth_tag is distinct from v_current.auth_tag
       or v_current_event.client_id is distinct from v_current.client_id
       or v_current_event.chain_version is distinct from v_current.chain_version
       or v_current_event.chain_tag is distinct from v_current.chain_tag then
      return jsonb_build_object(
        'status','unavailable',
        'reasonCode','witness-current-history-integrity-failed'
      );
    end if;

    v_history :=
      foundation.project_l_trace_witness_verify_history_v1(
        p_witness_id
      );
    if coalesce(v_history->>'status','')<>'verified' then
      return v_history;
    end if;

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
          'chainVersion',v_current.chain_version,
          'previousChainTag',v_current_event.previous_chain_tag,
          'chainTag',v_current.chain_tag,
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

  v_previous_chain_tag :=
    case
      when v_current.witness_id is null then repeat('0',64)
      else v_current.chain_tag
    end;

  if v_previous_chain_tag is null
     or v_previous_chain_tag !~ '^[a-f0-9]{64}$' then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','witness-chain-predecessor-unavailable'
    );
  end if;

  v_chain_material :=
    '{"chainVersion":1,"witnessId":"' || p_witness_id ||
    '","sequence":' || p_sequence::text ||
    ',"previousChainTag":"' || v_previous_chain_tag ||
    '","authKeyId":"' || v_auth_key_id ||
    '","authTag":"' || v_auth_tag ||
    '","headSha256":"' || p_head_sha256 ||
    '","generation":' || p_generation::text ||
    ',"keyset_sha256":"' || p_keyset_sha256 ||
    '","stateSha256":"' || p_state_sha256 ||
    '","clientId":"shine.companion"}';

  v_chain_tag := encode(
    extensions.hmac(
      'shine-ai:decision-trace-trust-state-witness-chain:v1' ||
      E'\n' || v_chain_material,
      v_secret,
      'sha256'
    ),
    'hex'
  );

  insert into foundation.project_l_trace_witness_events(
    witness_id,sequence,head_sha256,generation,keyset_sha256,state_sha256,
    auth_key_id,auth_tag,client_id,chain_version,previous_chain_tag,
    chain_tag,witnessed_at
  ) values (
    p_witness_id,p_sequence,p_head_sha256,p_generation,p_keyset_sha256,
    p_state_sha256,v_auth_key_id,v_auth_tag,'shine.companion',1,
    v_previous_chain_tag,v_chain_tag,pg_catalog.now()
  );

  insert into foundation.project_l_trace_witness_state(
    witness_id,sequence,head_sha256,generation,keyset_sha256,state_sha256,
    auth_key_id,auth_tag,client_id,chain_version,chain_tag,witnessed_at
  ) values (
    p_witness_id,p_sequence,p_head_sha256,p_generation,p_keyset_sha256,
    p_state_sha256,v_auth_key_id,v_auth_tag,'shine.companion',1,
    v_chain_tag,pg_catalog.now()
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
      chain_version=excluded.chain_version,
      chain_tag=excluded.chain_tag,
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
    'chainVersion',1,
    'previousChainTag',v_previous_chain_tag,
    'chainTag',v_chain_tag,
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
