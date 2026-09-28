-- Layer 211: Foundation external roster-head witness key overlap rotation.
-- Adds a second Foundation-only Vault HMAC key, makes the witness history
-- key-aware, preserves the exact roster-head truth across key rotation, and
-- keeps all secret material inside Foundation.

do $$
begin
  if not exists (
    select 1
    from vault.decrypted_secrets
    where name='project_l_external_roster_head_witness_hmac_v2'
  ) then
    perform vault.create_secret(
      encode(extensions.gen_random_bytes(48),'base64'),
      'project_l_external_roster_head_witness_hmac_v2',
      'Foundation-only overlap HMAC key for Project L external roster monotonic head witness rotation',
      null
    );
  end if;
end $$;

do $$
declare
  v_name text;
begin
  for v_name in
    select c.conname
    from pg_constraint c
    join pg_class t on t.oid=c.conrelid
    join pg_namespace n on n.oid=t.relnamespace
    where n.nspname='foundation'
      and t.relname='project_l_roster_head_witness_events'
      and c.contype='u'
      and pg_get_constraintdef(c.oid)='UNIQUE (witness_id, sequence)'
  loop
    execute format(
      'alter table foundation.project_l_roster_head_witness_events drop constraint %I',
      v_name
    );
  end loop;

  if not exists (
    select 1
    from pg_constraint c
    join pg_class t on t.oid=c.conrelid
    join pg_namespace n on n.oid=t.relnamespace
    where n.nspname='foundation'
      and t.relname='project_l_roster_head_witness_events'
      and c.contype='u'
      and pg_get_constraintdef(c.oid)=
        'UNIQUE (witness_id, sequence, auth_key_id)'
  ) then
    alter table foundation.project_l_roster_head_witness_events
      add constraint project_l_roster_head_witness_events_identity_key_v2
      unique (witness_id,sequence,auth_key_id);
  end if;
end $$;

create or replace function foundation.project_l_roster_head_witness_current_v1(
  p_client_token text,
  p_witness_id text default 'foundation-project-l-roster-head'
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, foundation, vault, extensions
as $$
declare
  v_token_hash text;
  v_state foundation.project_l_roster_head_witness_state%rowtype;
  v_event foundation.project_l_roster_head_witness_events%rowtype;
  v_secret_name text;
  v_secret text;
  v_material text;
  v_expected_tag text;
begin
  if p_client_token is null or length(p_client_token)<32
     or p_witness_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$' then
    return jsonb_build_object(
      'status','denied',
      'reasonCode','roster-head-witness-client-unverified'
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
      'reasonCode','roster-head-witness-client-unverified'
    );
  end if;

  select * into v_state
  from foundation.project_l_roster_head_witness_state s
  where s.witness_id=p_witness_id;

  if not found then
    return jsonb_build_object('status','empty','witnessId',p_witness_id);
  end if;

  v_secret_name := case v_state.auth_key_id
    when 'foundation-roster-head-witness-v1'
      then 'project_l_external_roster_head_witness_hmac_v1'
    when 'foundation-roster-head-witness-v2'
      then 'project_l_external_roster_head_witness_hmac_v2'
    else null
  end;

  if v_secret_name is null then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','roster-head-witness-signing-key-unknown'
    );
  end if;

  select decrypted_secret into v_secret
  from vault.decrypted_secrets
  where name=v_secret_name
  order by created_at desc
  limit 1;

  if v_secret is null or length(v_secret)<32 then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','roster-head-witness-signing-key-unavailable'
    );
  end if;

  v_material :=
    '{"witnessVersion":1,"witnessType":"decision_trace_trust_state_witness_quorum_policy_external_head_witness_quorum_monotonic_head_witness",' ||
    '"witnessId":"' || v_state.witness_id || '","headVersion":1,' ||
    '"sequence":' || v_state.sequence::text ||
    ',"headSha256":"' || v_state.head_sha256 ||
    '","generation":' || v_state.generation::text ||
    ',"policySha256":"' || v_state.policy_sha256 ||
    '","stateSha256":"' || v_state.state_sha256 || '"}';

  v_expected_tag := encode(
    extensions.hmac(
      'shine-ai:decision-trace-trust-state-witness-quorum-policy-external-head-witness-quorum-monotonic-head-witness:v1' ||
      E'\n' || v_state.auth_key_id || E'\n' || v_material,
      v_secret,
      'sha256'
    ),
    'hex'
  );

  if v_expected_tag<>v_state.auth_tag then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','roster-head-witness-auth-integrity-failed'
    );
  end if;

  select * into v_event
  from foundation.project_l_roster_head_witness_events e
  where e.witness_id=v_state.witness_id
    and e.sequence=v_state.sequence
    and e.auth_key_id=v_state.auth_key_id
  order by e.event_id desc
  limit 1;

  if not found
     or v_event.head_sha256 is distinct from v_state.head_sha256
     or v_event.generation is distinct from v_state.generation
     or v_event.policy_sha256 is distinct from v_state.policy_sha256
     or v_event.state_sha256 is distinct from v_state.state_sha256
     or v_event.auth_tag is distinct from v_state.auth_tag
     or v_event.client_id is distinct from v_state.client_id then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','roster-head-witness-history-integrity-failed'
    );
  end if;

  return jsonb_build_object(
    'status','witnessed',
    'witnessVersion',1,
    'witnessType',
      'decision_trace_trust_state_witness_quorum_policy_external_head_witness_quorum_monotonic_head_witness',
    'authAlgorithm','HMAC-SHA-256',
    'witnessId',v_state.witness_id,
    'authKeyId',v_state.auth_key_id,
    'headVersion',1,
    'sequence',v_state.sequence,
    'headSha256',v_state.head_sha256,
    'generation',v_state.generation,
    'policySha256',v_state.policy_sha256,
    'stateSha256',v_state.state_sha256,
    'authTag',v_state.auth_tag,
    'witnessedAt',v_state.witnessed_at
  );
end;
$$;

create or replace function foundation.project_l_roster_head_witness_record_v1(
  p_client_token text,
  p_witness_id text,
  p_sequence bigint,
  p_head_sha256 text,
  p_generation integer,
  p_policy_sha256 text,
  p_state_sha256 text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, foundation, vault, extensions
as $$
declare
  v_token_hash text;
  v_current foundation.project_l_roster_head_witness_state%rowtype;
  v_event foundation.project_l_roster_head_witness_events%rowtype;
  v_secret_name text;
  v_secret text;
  v_key_id text;
  v_material text;
  v_tag text;
  v_current_material text;
  v_current_tag text;
begin
  if p_client_token is null or length(p_client_token)<32
     or p_witness_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
     or p_sequence<1 or p_sequence>1000000
     or p_head_sha256 !~ '^[a-f0-9]{64}$'
     or p_generation<1 or p_generation>1000000
     or p_policy_sha256 !~ '^[a-f0-9]{64}$'
     or p_state_sha256 !~ '^[a-f0-9]{64}$' then
    return jsonb_build_object(
      'status','invalid',
      'reasonCode','roster-head-witness-request-invalid'
    );
  end if;

  if p_sequence<>p_generation then
    return jsonb_build_object(
      'status','invalid',
      'reasonCode','roster-head-witness-sequence-generation-mismatch'
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
      'reasonCode','roster-head-witness-client-unverified'
    );
  end if;

  perform pg_advisory_xact_lock(
    hashtext('foundation-project-l-roster-head-witness-v2')
  );

  select * into v_current
  from foundation.project_l_roster_head_witness_state s
  where s.witness_id=p_witness_id
  for update;

  if found then
    v_key_id := v_current.auth_key_id;
    v_secret_name := case v_key_id
      when 'foundation-roster-head-witness-v1'
        then 'project_l_external_roster_head_witness_hmac_v1'
      when 'foundation-roster-head-witness-v2'
        then 'project_l_external_roster_head_witness_hmac_v2'
      else null
    end;

    if v_secret_name is null then
      return jsonb_build_object(
        'status','unavailable',
        'reasonCode','roster-head-witness-signing-key-unknown'
      );
    end if;

    select decrypted_secret into v_secret
    from vault.decrypted_secrets
    where name=v_secret_name
    order by created_at desc
    limit 1;

    if v_secret is null or length(v_secret)<32 then
      return jsonb_build_object(
        'status','unavailable',
        'reasonCode','roster-head-witness-signing-key-unavailable'
      );
    end if;

    v_current_material :=
      '{"witnessVersion":1,"witnessType":"decision_trace_trust_state_witness_quorum_policy_external_head_witness_quorum_monotonic_head_witness",' ||
      '"witnessId":"' || v_current.witness_id || '","headVersion":1,' ||
      '"sequence":' || v_current.sequence::text ||
      ',"headSha256":"' || v_current.head_sha256 ||
      '","generation":' || v_current.generation::text ||
      ',"policySha256":"' || v_current.policy_sha256 ||
      '","stateSha256":"' || v_current.state_sha256 || '"}';

    v_current_tag := encode(
      extensions.hmac(
        'shine-ai:decision-trace-trust-state-witness-quorum-policy-external-head-witness-quorum-monotonic-head-witness:v1' ||
        E'\n' || v_current.auth_key_id || E'\n' || v_current_material,
        v_secret,
        'sha256'
      ),
      'hex'
    );

    if v_current_tag<>v_current.auth_tag then
      return jsonb_build_object(
        'status','unavailable',
        'reasonCode','roster-head-witness-current-auth-integrity-failed'
      );
    end if;

    select * into v_event
    from foundation.project_l_roster_head_witness_events e
    where e.witness_id=v_current.witness_id
      and e.sequence=v_current.sequence
      and e.auth_key_id=v_current.auth_key_id
    order by e.event_id desc
    limit 1;

    if not found
       or v_current.client_id<>'shine.companion'
       or v_event.head_sha256 is distinct from v_current.head_sha256
       or v_event.generation is distinct from v_current.generation
       or v_event.policy_sha256 is distinct from v_current.policy_sha256
       or v_event.state_sha256 is distinct from v_current.state_sha256
       or v_event.auth_tag is distinct from v_current.auth_tag
       or v_event.client_id is distinct from v_current.client_id then
      return jsonb_build_object(
        'status','unavailable',
        'reasonCode','roster-head-witness-current-history-integrity-failed'
      );
    end if;

    if p_sequence<v_current.sequence then
      return jsonb_build_object(
        'status','rejected',
        'reasonCode','roster-head-witness-sequence-rollback',
        'currentSequence',v_current.sequence
      );
    end if;

    if p_sequence=v_current.sequence then
      if p_head_sha256=v_current.head_sha256
         and p_generation=v_current.generation
         and p_policy_sha256=v_current.policy_sha256
         and p_state_sha256=v_current.state_sha256 then
        return jsonb_build_object(
          'status','witnessed',
          'replayed',true,
          'witnessVersion',1,
          'witnessType',
            'decision_trace_trust_state_witness_quorum_policy_external_head_witness_quorum_monotonic_head_witness',
          'authAlgorithm','HMAC-SHA-256',
          'witnessId',v_current.witness_id,
          'authKeyId',v_current.auth_key_id,
          'headVersion',1,
          'sequence',v_current.sequence,
          'headSha256',v_current.head_sha256,
          'generation',v_current.generation,
          'policySha256',v_current.policy_sha256,
          'stateSha256',v_current.state_sha256,
          'authTag',v_current.auth_tag,
          'witnessedAt',v_current.witnessed_at
        );
      end if;
      return jsonb_build_object(
        'status','rejected',
        'reasonCode','roster-head-witness-sequence-equivocation',
        'currentSequence',v_current.sequence
      );
    end if;

    if p_sequence<>v_current.sequence+1
       or p_generation<>v_current.generation+1 then
      return jsonb_build_object(
        'status','rejected',
        'reasonCode','roster-head-witness-sequence-skip',
        'currentSequence',v_current.sequence,
        'currentGeneration',v_current.generation
      );
    end if;

    if p_policy_sha256=v_current.policy_sha256 then
      return jsonb_build_object(
        'status','rejected',
        'reasonCode','roster-head-witness-generation-without-policy-change'
      );
    end if;
    if p_state_sha256=v_current.state_sha256 then
      return jsonb_build_object(
        'status','rejected',
        'reasonCode','roster-head-witness-state-not-advanced'
      );
    end if;
  else
    v_key_id := 'foundation-roster-head-witness-v1';
    v_secret_name := 'project_l_external_roster_head_witness_hmac_v1';
    select decrypted_secret into v_secret
    from vault.decrypted_secrets
    where name=v_secret_name
    order by created_at desc
    limit 1;

    if p_sequence<>1 or p_generation<>1 then
      return jsonb_build_object(
        'status','rejected',
        'reasonCode','roster-head-witness-genesis-invalid'
      );
    end if;
  end if;

  if v_secret is null or length(v_secret)<32 then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','roster-head-witness-signing-key-unavailable'
    );
  end if;

  v_material :=
    '{"witnessVersion":1,"witnessType":"decision_trace_trust_state_witness_quorum_policy_external_head_witness_quorum_monotonic_head_witness",' ||
    '"witnessId":"' || p_witness_id || '","headVersion":1,' ||
    '"sequence":' || p_sequence::text ||
    ',"headSha256":"' || p_head_sha256 ||
    '","generation":' || p_generation::text ||
    ',"policySha256":"' || p_policy_sha256 ||
    '","stateSha256":"' || p_state_sha256 || '"}';

  v_tag := encode(
    extensions.hmac(
      'shine-ai:decision-trace-trust-state-witness-quorum-policy-external-head-witness-quorum-monotonic-head-witness:v1' ||
      E'\n' || v_key_id || E'\n' || v_material,
      v_secret,
      'sha256'
    ),
    'hex'
  );

  insert into foundation.project_l_roster_head_witness_events(
    witness_id,sequence,head_sha256,generation,policy_sha256,state_sha256,
    auth_key_id,auth_tag,client_id,witnessed_at
  ) values (
    p_witness_id,p_sequence,p_head_sha256,p_generation,p_policy_sha256,
    p_state_sha256,v_key_id,v_tag,'shine.companion',pg_catalog.now()
  )
  on conflict (witness_id,sequence,auth_key_id) do update
  set head_sha256=excluded.head_sha256,
      generation=excluded.generation,
      policy_sha256=excluded.policy_sha256,
      state_sha256=excluded.state_sha256,
      auth_tag=excluded.auth_tag,
      client_id=excluded.client_id,
      witnessed_at=excluded.witnessed_at;

  insert into foundation.project_l_roster_head_witness_state(
    witness_id,sequence,head_sha256,generation,policy_sha256,state_sha256,
    auth_key_id,auth_tag,client_id,witnessed_at
  ) values (
    p_witness_id,p_sequence,p_head_sha256,p_generation,p_policy_sha256,
    p_state_sha256,v_key_id,v_tag,'shine.companion',pg_catalog.now()
  )
  on conflict (witness_id) do update
  set sequence=excluded.sequence,
      head_sha256=excluded.head_sha256,
      generation=excluded.generation,
      policy_sha256=excluded.policy_sha256,
      state_sha256=excluded.state_sha256,
      auth_key_id=excluded.auth_key_id,
      auth_tag=excluded.auth_tag,
      client_id=excluded.client_id,
      witnessed_at=excluded.witnessed_at;

  return jsonb_build_object(
    'status','witnessed',
    'replayed',false,
    'witnessVersion',1,
    'witnessType',
      'decision_trace_trust_state_witness_quorum_policy_external_head_witness_quorum_monotonic_head_witness',
    'authAlgorithm','HMAC-SHA-256',
    'witnessId',p_witness_id,
    'authKeyId',v_key_id,
    'headVersion',1,
    'sequence',p_sequence,
    'headSha256',p_head_sha256,
    'generation',p_generation,
    'policySha256',p_policy_sha256,
    'stateSha256',p_state_sha256,
    'authTag',v_tag,
    'witnessedAt',pg_catalog.now()
  );
end;
$$;

create or replace function foundation.project_l_roster_head_witness_rotate_v2(
  p_client_token text,
  p_witness_id text,
  p_target_auth_key_id text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, foundation, vault, extensions
as $$
declare
  v_token_hash text;
  v_current foundation.project_l_roster_head_witness_state%rowtype;
  v_event foundation.project_l_roster_head_witness_events%rowtype;
  v_source_secret_name text;
  v_target_secret_name text;
  v_source_secret text;
  v_target_secret text;
  v_material text;
  v_source_tag text;
  v_target_tag text;
  v_now timestamptz := pg_catalog.now();
begin
  if p_client_token is null or length(p_client_token)<32
     or p_witness_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
     or p_target_auth_key_id not in (
       'foundation-roster-head-witness-v1',
       'foundation-roster-head-witness-v2'
     ) then
    return jsonb_build_object(
      'status','invalid',
      'reasonCode','roster-head-witness-rotation-request-invalid'
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
      'reasonCode','roster-head-witness-client-unverified'
    );
  end if;

  perform pg_advisory_xact_lock(
    hashtext('foundation-project-l-roster-head-witness-v2')
  );

  select * into v_current
  from foundation.project_l_roster_head_witness_state s
  where s.witness_id=p_witness_id
  for update;

  if not found then
    return jsonb_build_object(
      'status','rejected',
      'reasonCode','roster-head-witness-rotation-source-missing'
    );
  end if;

  if v_current.auth_key_id=p_target_auth_key_id then
    return jsonb_build_object(
      'status','rejected',
      'reasonCode','roster-head-witness-rotation-noop'
    );
  end if;

  v_source_secret_name := case v_current.auth_key_id
    when 'foundation-roster-head-witness-v1'
      then 'project_l_external_roster_head_witness_hmac_v1'
    when 'foundation-roster-head-witness-v2'
      then 'project_l_external_roster_head_witness_hmac_v2'
    else null
  end;
  v_target_secret_name := case p_target_auth_key_id
    when 'foundation-roster-head-witness-v1'
      then 'project_l_external_roster_head_witness_hmac_v1'
    when 'foundation-roster-head-witness-v2'
      then 'project_l_external_roster_head_witness_hmac_v2'
    else null
  end;

  if v_source_secret_name is null or v_target_secret_name is null then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','roster-head-witness-rotation-key-unknown'
    );
  end if;

  select decrypted_secret into v_source_secret
  from vault.decrypted_secrets
  where name=v_source_secret_name
  order by created_at desc
  limit 1;

  select decrypted_secret into v_target_secret
  from vault.decrypted_secrets
  where name=v_target_secret_name
  order by created_at desc
  limit 1;

  if v_source_secret is null or length(v_source_secret)<32
     or v_target_secret is null or length(v_target_secret)<32 then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','roster-head-witness-rotation-key-unavailable'
    );
  end if;

  v_material :=
    '{"witnessVersion":1,"witnessType":"decision_trace_trust_state_witness_quorum_policy_external_head_witness_quorum_monotonic_head_witness",' ||
    '"witnessId":"' || v_current.witness_id || '","headVersion":1,' ||
    '"sequence":' || v_current.sequence::text ||
    ',"headSha256":"' || v_current.head_sha256 ||
    '","generation":' || v_current.generation::text ||
    ',"policySha256":"' || v_current.policy_sha256 ||
    '","stateSha256":"' || v_current.state_sha256 || '"}';

  v_source_tag := encode(
    extensions.hmac(
      'shine-ai:decision-trace-trust-state-witness-quorum-policy-external-head-witness-quorum-monotonic-head-witness:v1' ||
      E'\n' || v_current.auth_key_id || E'\n' || v_material,
      v_source_secret,
      'sha256'
    ),
    'hex'
  );

  if v_source_tag<>v_current.auth_tag then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','roster-head-witness-rotation-source-auth-failed'
    );
  end if;

  select * into v_event
  from foundation.project_l_roster_head_witness_events e
  where e.witness_id=v_current.witness_id
    and e.sequence=v_current.sequence
    and e.auth_key_id=v_current.auth_key_id
  order by e.event_id desc
  limit 1;

  if not found
     or v_event.head_sha256 is distinct from v_current.head_sha256
     or v_event.generation is distinct from v_current.generation
     or v_event.policy_sha256 is distinct from v_current.policy_sha256
     or v_event.state_sha256 is distinct from v_current.state_sha256
     or v_event.auth_tag is distinct from v_current.auth_tag
     or v_event.client_id is distinct from v_current.client_id then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','roster-head-witness-rotation-source-history-failed'
    );
  end if;

  v_target_tag := encode(
    extensions.hmac(
      'shine-ai:decision-trace-trust-state-witness-quorum-policy-external-head-witness-quorum-monotonic-head-witness:v1' ||
      E'\n' || p_target_auth_key_id || E'\n' || v_material,
      v_target_secret,
      'sha256'
    ),
    'hex'
  );

  insert into foundation.project_l_roster_head_witness_events(
    witness_id,sequence,head_sha256,generation,policy_sha256,state_sha256,
    auth_key_id,auth_tag,client_id,witnessed_at
  ) values (
    v_current.witness_id,v_current.sequence,v_current.head_sha256,
    v_current.generation,v_current.policy_sha256,v_current.state_sha256,
    p_target_auth_key_id,v_target_tag,v_current.client_id,v_now
  )
  on conflict (witness_id,sequence,auth_key_id) do update
  set head_sha256=excluded.head_sha256,
      generation=excluded.generation,
      policy_sha256=excluded.policy_sha256,
      state_sha256=excluded.state_sha256,
      auth_tag=excluded.auth_tag,
      client_id=excluded.client_id,
      witnessed_at=excluded.witnessed_at;

  update foundation.project_l_roster_head_witness_state
  set auth_key_id=p_target_auth_key_id,
      auth_tag=v_target_tag,
      witnessed_at=v_now
  where witness_id=v_current.witness_id
    and sequence=v_current.sequence
    and head_sha256=v_current.head_sha256
    and generation=v_current.generation
    and policy_sha256=v_current.policy_sha256
    and state_sha256=v_current.state_sha256
    and auth_key_id=v_current.auth_key_id
    and auth_tag=v_current.auth_tag;

  if not found then
    return jsonb_build_object(
      'status','unavailable',
      'reasonCode','roster-head-witness-rotation-commit-failed'
    );
  end if;

  return jsonb_build_object(
    'status','rotated',
    'receipt',jsonb_build_object(
      'version',1,
      'eventType',
        'decision_trace_trust_state_witness_quorum_policy_monotonic_head_witness_key_rotation',
      'witnessId',v_current.witness_id,
      'sourceAuthKeyId',v_current.auth_key_id,
      'targetAuthKeyId',p_target_auth_key_id,
      'sequence',v_current.sequence,
      'headSha256',v_current.head_sha256,
      'generation',v_current.generation,
      'policySha256',v_current.policy_sha256,
      'stateSha256',v_current.state_sha256
    ),
    'witness',jsonb_build_object(
      'status','witnessed',
      'witnessVersion',1,
      'witnessType',
        'decision_trace_trust_state_witness_quorum_policy_external_head_witness_quorum_monotonic_head_witness',
      'authAlgorithm','HMAC-SHA-256',
      'witnessId',v_current.witness_id,
      'authKeyId',p_target_auth_key_id,
      'headVersion',1,
      'sequence',v_current.sequence,
      'headSha256',v_current.head_sha256,
      'generation',v_current.generation,
      'policySha256',v_current.policy_sha256,
      'stateSha256',v_current.state_sha256,
      'authTag',v_target_tag,
      'witnessedAt',v_now
    )
  );
end;
$$;

revoke all on function
 foundation.project_l_roster_head_witness_rotate_v2(text,text,text)
 from public, anon, authenticated, foundation_runtime, shine_defence_runtime;

grant execute on function
 foundation.project_l_roster_head_witness_rotate_v2(text,text,text)
 to foundation_gateway;
