-- Layer 208: durable, independently verifiable roster-transition evidence.
-- Stores the exact bounded authorization envelopes used for each future roster
-- generation. Direct table access is denied; service_role can only write/read
-- through security-definer RPCs. Genesis has no transition evidence.

create table if not exists public.shine_ai_external_roster_transition_evidence (
  generation integer primary key check (generation between 2 and 1000000),
  previous_policy_sha256 text not null
    check (previous_policy_sha256 ~ '^[a-f0-9]{64}$'),
  policy_sha256 text not null
    check (policy_sha256 ~ '^[a-f0-9]{64}$'),
  authorization_sha256 text not null
    check (authorization_sha256 ~ '^[a-f0-9]{64}$'),
  authorizing_witness_ids text[] not null,
  authorizations jsonb not null,
  recorded_at timestamptz not null default now()
);

alter table public.shine_ai_external_roster_transition_evidence
  enable row level security;
revoke all on public.shine_ai_external_roster_transition_evidence
  from public, anon, authenticated, service_role;

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
set search_path = pg_catalog, public
as $$
declare
  v_ledger public.shine_ai_external_witness_roster_ledger%rowtype;
  v_existing public.shine_ai_external_roster_transition_evidence%rowtype;
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

  select * into v_existing
  from public.shine_ai_external_roster_transition_evidence
  where generation=p_generation;

  if found then
    if v_existing.previous_policy_sha256=p_previous_policy_sha256
       and v_existing.policy_sha256=p_policy_sha256
       and v_existing.authorization_sha256=p_authorization_sha256
       and v_existing.authorizing_witness_ids=p_authorizing_witness_ids
       and v_existing.authorizations=p_authorizations then
      return jsonb_build_object(
        'status','verified',
        'mode','existing',
        'generation',p_generation
      );
    end if;
    return jsonb_build_object(
      'status','rejected',
      'reason_code','external-roster-transition-evidence-equivocation'
    );
  end if;

  insert into public.shine_ai_external_roster_transition_evidence(
    generation,previous_policy_sha256,policy_sha256,
    authorization_sha256,authorizing_witness_ids,authorizations
  ) values (
    p_generation,p_previous_policy_sha256,p_policy_sha256,
    p_authorization_sha256,p_authorizing_witness_ids,p_authorizations
  );

  return jsonb_build_object(
    'status','verified',
    'mode','recorded',
    'generation',p_generation
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
    'authorizations',v_row.authorizations
  );
end;
$$;

revoke all on function
 public.shine_ai_external_roster_transition_evidence_record_v1(
   integer,text,text,text,text[],jsonb
 ) from public, anon, authenticated;
revoke all on function
 public.shine_ai_external_roster_transition_evidence_v1(integer)
 from public, anon, authenticated;
grant execute on function
 public.shine_ai_external_roster_transition_evidence_record_v1(
   integer,text,text,text,text[],jsonb
 ) to service_role;
grant execute on function
 public.shine_ai_external_roster_transition_evidence_v1(integer)
 to service_role;
