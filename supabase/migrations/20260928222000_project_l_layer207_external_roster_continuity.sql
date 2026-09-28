-- Layer 207: governed external-witness-roster N -> N+1 transitions.
-- A roster may advance only one generation, must link to the prior roster
-- digest, and must carry distinct authorization from the previous roster's
-- threshold of accepted witnesses.

alter table public.shine_ai_external_witness_roster_ledger
  drop constraint if exists
    shine_ai_external_witness_roster_ledger_acceptance_mode_check;

alter table public.shine_ai_external_witness_roster_ledger
  add constraint shine_ai_external_witness_roster_ledger_acceptance_mode_check
  check (acceptance_mode in ('genesis-pin','previous-roster-quorum'));

alter table public.shine_ai_external_witness_roster_ledger
  add column if not exists authorizing_witness_ids text[],
  add column if not exists authorization_sha256 text;

create or replace function public.shine_ai_external_witness_roster_advance_v2(
    p_expected_generation integer,
    p_expected_policy_sha256 text,
    p_next_generation integer,
    p_next_minimum_witnesses integer,
    p_next_accepted_witness_ids text[],
    p_next_previous_policy_sha256 text,
    p_next_policy_sha256 text,
    p_authorizing_witness_ids text[],
    p_authorization_sha256 text,
    p_state_sha256 text,
    p_storage_auth_key_id text,
    p_storage_auth_tag text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_current public.shine_ai_external_witness_roster_state%rowtype;
    v_distinct_auth_count integer;
begin
    perform pg_advisory_xact_lock(
      hashtext('shine-ai-external-witness-roster-v1')
    );

    select * into v_current
    from public.shine_ai_external_witness_roster_state
    where singleton=true
    for update;

    if not found then
        return jsonb_build_object(
          'status','rejected',
          'reason_code','external-witness-roster-transition-missing-current'
        );
    end if;

    if v_current.generation<>p_expected_generation
       or v_current.policy_sha256<>p_expected_policy_sha256 then
        return jsonb_build_object(
          'status','rejected',
          'reason_code','external-witness-roster-transition-stale-current'
        );
    end if;

    if p_next_generation<>v_current.generation+1
       or p_next_previous_policy_sha256<>v_current.policy_sha256
       or p_next_minimum_witnesses<2
       or p_next_minimum_witnesses>cardinality(p_next_accepted_witness_ids)
       or cardinality(p_next_accepted_witness_ids) not between 2 and 4
       or p_next_policy_sha256 !~ '^[a-f0-9]{64}$'
       or p_state_sha256 !~ '^[a-f0-9]{64}$'
       or p_storage_auth_key_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
       or p_storage_auth_tag !~ '^[a-f0-9]{64}$'
       or p_authorization_sha256 !~ '^[a-f0-9]{64}$' then
        return jsonb_build_object(
          'status','rejected',
          'reason_code','external-witness-roster-transition-invalid'
        );
    end if;

    if exists (
      select 1
      from unnest(p_authorizing_witness_ids) as x(witness_id)
      where not (x.witness_id=any(v_current.accepted_witness_ids))
    ) then
        return jsonb_build_object(
          'status','rejected',
          'reason_code','external-witness-roster-transition-authorizer-not-previous'
        );
    end if;

    select count(distinct x.witness_id)
    into v_distinct_auth_count
    from unnest(p_authorizing_witness_ids) as x(witness_id);

    if v_distinct_auth_count<v_current.minimum_witnesses then
        return jsonb_build_object(
          'status','rejected',
          'reason_code','external-witness-roster-transition-authorizations-insufficient'
        );
    end if;

    insert into public.shine_ai_external_witness_roster_ledger(
      generation,minimum_witnesses,accepted_witness_ids,
      previous_policy_sha256,policy_sha256,state_sha256,
      storage_auth_key_id,acceptance_mode,authorizing_witness_ids,
      authorization_sha256,accepted_at
    ) values (
      p_next_generation,p_next_minimum_witnesses,
      p_next_accepted_witness_ids,p_next_previous_policy_sha256,
      p_next_policy_sha256,p_state_sha256,p_storage_auth_key_id,
      'previous-roster-quorum',p_authorizing_witness_ids,
      p_authorization_sha256,now()
    );

    update public.shine_ai_external_witness_roster_state
    set generation=p_next_generation,
        minimum_witnesses=p_next_minimum_witnesses,
        accepted_witness_ids=p_next_accepted_witness_ids,
        previous_policy_sha256=p_next_previous_policy_sha256,
        policy_sha256=p_next_policy_sha256,
        source='genesis-pin',
        state_sha256=p_state_sha256,
        storage_auth_key_id=p_storage_auth_key_id,
        storage_auth_tag=p_storage_auth_tag,
        updated_at=now()
    where singleton=true;

    return jsonb_build_object(
      'status','trusted',
      'trust_state',jsonb_build_object(
        'trustStateVersion',1,
        'trustStateType',
          'decision_trace_trust_state_witness_quorum_policy_external_head_witness_quorum_policy',
        'generation',p_next_generation,
        'minimumWitnesses',p_next_minimum_witnesses,
        'acceptedWitnessIds',to_jsonb(p_next_accepted_witness_ids),
        'previousPolicySha256',p_next_previous_policy_sha256,
        'policySha256',p_next_policy_sha256
      ),
      'acceptance',jsonb_build_object(
        'mode','previous-roster-quorum',
        'authorizingWitnessIds',to_jsonb(p_authorizing_witness_ids),
        'authorizationSha256',p_authorization_sha256
      )
    );
end;
$$;

revoke all on function
 public.shine_ai_external_witness_roster_advance_v2(
   integer,text,integer,integer,text[],text,text,text[],text,text,text,text
 )
 from public, anon, authenticated;

grant execute on function
 public.shine_ai_external_witness_roster_advance_v2(
   integer,text,integer,integer,text[],text,text,text[],text,text,text,text
 )
 to service_role;
