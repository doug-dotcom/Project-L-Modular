-- Layer 211: Vault-HMAC chain across external-roster transition evidence.
-- Generation 1 has no transition evidence. The first evidence row is generation 2
-- and is anchored to the zero predecessor. Every later row must chain to the
-- immediately previous evidence row and the full chain is reverified on read.

do $$
begin
  if not exists (
    select 1
    from vault.decrypted_secrets
    where name='project_l_external_roster_transition_evidence_chain_hmac_v1'
  ) then
    perform vault.create_secret(
      encode(extensions.gen_random_bytes(48),'base64'),
      'project_l_external_roster_transition_evidence_chain_hmac_v1',
      'Project L Vault key for external roster transition evidence chain',
      null
    );
  end if;
end $$;

alter table public.shine_ai_external_roster_transition_evidence
  add column if not exists evidence_sha256 text,
  add column if not exists chain_version integer,
  add column if not exists previous_chain_tag text,
  add column if not exists chain_tag text,
  add column if not exists chain_auth_key_id text;

do $$
declare
  v_secret text;
  v_row record;
  v_previous_chain_tag text := repeat('0',64);
  v_previous_policy_sha256 text := null;
  v_evidence_material jsonb;
  v_evidence_sha256 text;
  v_chain_material jsonb;
  v_chain_tag text;
  v_key_id text := 'project-l-roster-evidence-chain-v1';
begin
  select decrypted_secret into v_secret
  from vault.decrypted_secrets
  where name='project_l_external_roster_transition_evidence_chain_hmac_v1'
  order by created_at desc
  limit 1;

  if v_secret is null or length(v_secret)<32 then
    raise exception 'external-roster-evidence-chain-key-unavailable';
  end if;

  for v_row in
    select *
    from public.shine_ai_external_roster_transition_evidence
    order by generation
  loop
    if v_row.generation=2 then
      if v_row.previous_policy_sha256 is null then
        raise exception 'external-roster-evidence-chain-genesis-invalid';
      end if;
    else
      if v_previous_policy_sha256 is null
         or v_row.previous_policy_sha256<>v_previous_policy_sha256 then
        raise exception 'external-roster-evidence-chain-predecessor-policy-mismatch';
      end if;
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
    v_chain_material := jsonb_build_object(
      'chainVersion',1,
      'generation',v_row.generation,
      'previousChainTag',v_previous_chain_tag,
      'evidenceSha256',v_evidence_sha256,
      'previousPolicySha256',v_row.previous_policy_sha256,
      'policySha256',v_row.policy_sha256,
      'authorizationSha256',v_row.authorization_sha256
    );
    v_chain_tag := encode(
      extensions.hmac(
        'shine:project-l:external-roster-transition-evidence-chain:v1' ||
        E'\n' || v_key_id || E'\n' || v_chain_material::text,
        v_secret,
        'sha256'
      ),
      'hex'
    );

    update public.shine_ai_external_roster_transition_evidence
    set evidence_sha256=v_evidence_sha256,
        chain_version=1,
        previous_chain_tag=v_previous_chain_tag,
        chain_tag=v_chain_tag,
        chain_auth_key_id=v_key_id
    where generation=v_row.generation;

    v_previous_chain_tag := v_chain_tag;
    v_previous_policy_sha256 := v_row.policy_sha256;
  end loop;
end $$;

alter table public.shine_ai_external_roster_transition_evidence
  alter column evidence_sha256 set not null,
  alter column chain_version set not null,
  alter column previous_chain_tag set not null,
  alter column chain_tag set not null,
  alter column chain_auth_key_id set not null;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname='shine_ai_external_roster_transition_evidence_evidence_sha_check'
      and conrelid='public.shine_ai_external_roster_transition_evidence'::regclass
  ) then
    alter table public.shine_ai_external_roster_transition_evidence
      add constraint shine_ai_external_roster_transition_evidence_evidence_sha_check
      check (evidence_sha256 ~ '^[a-f0-9]{64}$');
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname='shine_ai_external_roster_transition_evidence_chain_version_check'
      and conrelid='public.shine_ai_external_roster_transition_evidence'::regclass
  ) then
    alter table public.shine_ai_external_roster_transition_evidence
      add constraint shine_ai_external_roster_transition_evidence_chain_version_check
      check (chain_version=1);
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname='shine_ai_external_roster_transition_evidence_previous_chain_check'
      and conrelid='public.shine_ai_external_roster_transition_evidence'::regclass
  ) then
    alter table public.shine_ai_external_roster_transition_evidence
      add constraint shine_ai_external_roster_transition_evidence_previous_chain_check
      check (previous_chain_tag ~ '^[a-f0-9]{64}$');
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname='shine_ai_external_roster_transition_evidence_chain_tag_check'
      and conrelid='public.shine_ai_external_roster_transition_evidence'::regclass
  ) then
    alter table public.shine_ai_external_roster_transition_evidence
      add constraint shine_ai_external_roster_transition_evidence_chain_tag_check
      check (chain_tag ~ '^[a-f0-9]{64}$');
  end if;
end $$;

create or replace function public.shine_ai_external_roster_transition_evidence_record_v1(
  p_generation integer,
  p_previous_policy_sha256 text,
  p_policy_sha256 text,
  p_authorization_sha256 text,
  p_authorizing_witness_ids text[],
  p_authorizations jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, vault, extensions
as $$
declare
  v_ledger public.shine_ai_external_witness_roster_ledger%rowtype;
  v_existing public.shine_ai_external_roster_transition_evidence%rowtype;
  v_previous public.shine_ai_external_roster_transition_evidence%rowtype;
  v_secret text;
  v_key_id text := 'project-l-roster-evidence-chain-v1';
  v_previous_chain_tag text;
  v_evidence_material jsonb;
  v_evidence_sha256 text;
  v_chain_material jsonb;
  v_chain_tag text;
begin
  if p_generation<2
     or p_previous_policy_sha256 !~ '^[a-f0-9]{64}$'
     or p_policy_sha256 !~ '^[a-f0-9]{64}$'
     or p_authorization_sha256 !~ '^[a-f0-9]{64}$'
     or jsonb_typeof(p_authorizations)<>'array'
     or jsonb_array_length(p_authorizations) not between 2 and 4
     or cardinality(p_authorizing_witness_ids)
        <> jsonb_array_length(p_authorizations) then
    return jsonb_build_object(
      'status','invalid',
      'reason_code','external-roster-transition-evidence-invalid'
    );
  end if;

  select * into v_ledger
  from public.shine_ai_external_witness_roster_ledger
  where generation=p_generation;

  if not found
     or v_ledger.acceptance_mode<>'previous-roster-quorum'
     or v_ledger.previous_policy_sha256<>p_previous_policy_sha256
     or v_ledger.policy_sha256<>p_policy_sha256
     or v_ledger.authorization_sha256<>p_authorization_sha256
     or v_ledger.authorizing_witness_ids<>p_authorizing_witness_ids then
    return jsonb_build_object(
      'status','rejected',
      'reason_code','external-roster-transition-evidence-ledger-mismatch'
    );
  end if;

  if exists (
    select 1
    from jsonb_array_elements(p_authorizations) a
    where a->>'witnessId' is null
       or a->>'authAlgorithm'<>'HMAC-SHA-256'
       or a->>'authTag' !~ '^[a-f0-9]{64}$'
       or (a->>'fromGeneration')::integer<>p_generation-1
       or (a->>'toGeneration')::integer<>p_generation
       or a->>'fromPolicySha256'<>p_previous_policy_sha256
       or a->>'toPolicySha256'<>p_policy_sha256
  ) then
    return jsonb_build_object(
      'status','rejected',
      'reason_code','external-roster-transition-evidence-envelope-mismatch'
    );
  end if;

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

  if p_generation=2 then
    v_previous_chain_tag := repeat('0',64);
  else
    select * into v_previous
    from public.shine_ai_external_roster_transition_evidence
    where generation=p_generation-1;
    if not found
       or v_previous.policy_sha256<>p_previous_policy_sha256 then
      return jsonb_build_object(
        'status','rejected',
        'reason_code','external-roster-transition-evidence-chain-predecessor-missing'
      );
    end if;
    v_previous_chain_tag := v_previous.chain_tag;
  end if;

  v_evidence_material := jsonb_build_object(
    'evidenceVersion',1,
    'generation',p_generation,
    'previousPolicySha256',p_previous_policy_sha256,
    'policySha256',p_policy_sha256,
    'authorizationSha256',p_authorization_sha256,
    'authorizingWitnessIds',to_jsonb(p_authorizing_witness_ids),
    'authorizations',p_authorizations
  );
  v_evidence_sha256 := encode(
    extensions.digest(v_evidence_material::text,'sha256'),
    'hex'
  );
  v_chain_material := jsonb_build_object(
    'chainVersion',1,
    'generation',p_generation,
    'previousChainTag',v_previous_chain_tag,
    'evidenceSha256',v_evidence_sha256,
    'previousPolicySha256',p_previous_policy_sha256,
    'policySha256',p_policy_sha256,
    'authorizationSha256',p_authorization_sha256
  );
  v_chain_tag := encode(
    extensions.hmac(
      'shine:project-l:external-roster-transition-evidence-chain:v1' ||
      E'\n' || v_key_id || E'\n' || v_chain_material::text,
      v_secret,
      'sha256'
    ),
    'hex'
  );

  select * into v_existing
  from public.shine_ai_external_roster_transition_evidence
  where generation=p_generation;

  if found then
    if v_existing.previous_policy_sha256=p_previous_policy_sha256
       and v_existing.policy_sha256=p_policy_sha256
       and v_existing.authorization_sha256=p_authorization_sha256
       and v_existing.authorizing_witness_ids=p_authorizing_witness_ids
       and v_existing.authorizations=p_authorizations
       and v_existing.evidence_sha256=v_evidence_sha256
       and v_existing.chain_version=1
       and v_existing.previous_chain_tag=v_previous_chain_tag
       and v_existing.chain_tag=v_chain_tag
       and v_existing.chain_auth_key_id=v_key_id then
      return jsonb_build_object(
        'status','verified',
        'mode','existing',
        'generation',p_generation,
        'evidenceSha256',v_existing.evidence_sha256,
        'chainVersion',v_existing.chain_version,
        'previousChainTag',v_existing.previous_chain_tag,
        'chainTag',v_existing.chain_tag
      );
    end if;
    return jsonb_build_object(
      'status','rejected',
      'reason_code','external-roster-transition-evidence-equivocation'
    );
  end if;

  insert into public.shine_ai_external_roster_transition_evidence(
    generation,previous_policy_sha256,policy_sha256,
    authorization_sha256,authorizing_witness_ids,authorizations,
    evidence_sha256,chain_version,previous_chain_tag,chain_tag,
    chain_auth_key_id
  ) values (
    p_generation,p_previous_policy_sha256,p_policy_sha256,
    p_authorization_sha256,p_authorizing_witness_ids,p_authorizations,
    v_evidence_sha256,1,v_previous_chain_tag,v_chain_tag,v_key_id
  );

  return jsonb_build_object(
    'status','verified',
    'mode','recorded',
    'generation',p_generation,
    'evidenceSha256',v_evidence_sha256,
    'chainVersion',1,
    'previousChainTag',v_previous_chain_tag,
    'chainTag',v_chain_tag
  );
end;
$$;

create or replace function public.shine_ai_external_roster_transition_evidence_v1(
  p_generation integer
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_row public.shine_ai_external_roster_transition_evidence%rowtype;
begin
  select * into v_row
  from public.shine_ai_external_roster_transition_evidence
  where generation=p_generation;
  if not found then
    return jsonb_build_object('status','empty','generation',p_generation);
  end if;
  return jsonb_build_object(
    'status','verified',
    'generation',v_row.generation,
    'previousPolicySha256',v_row.previous_policy_sha256,
    'policySha256',v_row.policy_sha256,
    'authorizationSha256',v_row.authorization_sha256,
    'authorizingWitnessIds',to_jsonb(v_row.authorizing_witness_ids),
    'authorizations',v_row.authorizations,
    'evidenceSha256',v_row.evidence_sha256,
    'chainVersion',v_row.chain_version,
    'previousChainTag',v_row.previous_chain_tag,
    'chainTag',v_row.chain_tag,
    'chainAuthKeyId',v_row.chain_auth_key_id
  );
end;
$$;

create or replace function public.shine_ai_external_roster_transition_evidence_chain_verify_v1()
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
        E'\n' || v_row.chain_auth_key_id || E'\n' || v_chain_material::text,
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
