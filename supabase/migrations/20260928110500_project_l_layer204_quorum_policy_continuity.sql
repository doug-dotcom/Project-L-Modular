-- Layer 204: previous-quorum-authorised witness-policy continuity
-- on top of Layer 202 authenticated policy storage.
--
-- Production remains generation 1. This adds only a bounded N -> N+1 path.
-- The independent Redis policy checkpoint must be advanced by the runtime
-- before this RPC commits the authenticated Supabase high-water state.

alter table public.shine_ai_witness_quorum_policy_state
  drop constraint if exists shine_ai_witness_quorum_policy_state_source_check;
alter table public.shine_ai_witness_quorum_policy_state
  add constraint shine_ai_witness_quorum_policy_state_source_check
  check (source in ('genesis-pin','previous-quorum-transition'));

alter table public.shine_ai_witness_quorum_policy_ledger
  drop constraint if exists shine_ai_witness_quorum_policy_ledger_acceptance_mode_check;
alter table public.shine_ai_witness_quorum_policy_ledger
  add constraint shine_ai_witness_quorum_policy_ledger_acceptance_mode_check
  check (acceptance_mode in ('genesis-pin','previous-quorum-transition'));

alter table public.shine_ai_witness_quorum_policy_ledger
  add column if not exists authorizing_witness_ids text[],
  add column if not exists authorization_sha256 text;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname='shine_ai_witness_quorum_policy_ledger_authorizers_ck'
  ) then
    alter table public.shine_ai_witness_quorum_policy_ledger
      add constraint shine_ai_witness_quorum_policy_ledger_authorizers_ck
      check (
        authorizing_witness_ids is null
        or cardinality(authorizing_witness_ids) between 2 and 4
      );
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname='shine_ai_witness_quorum_policy_ledger_authorization_sha_ck'
  ) then
    alter table public.shine_ai_witness_quorum_policy_ledger
      add constraint shine_ai_witness_quorum_policy_ledger_authorization_sha_ck
      check (
        authorization_sha256 is null
        or authorization_sha256 ~ '^[a-f0-9]{64}$'
      );
  end if;
end $$;

create or replace function public.shine_ai_witness_quorum_policy_snapshot_v3()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_state public.shine_ai_witness_quorum_policy_state%rowtype;
  v_ledger public.shine_ai_witness_quorum_policy_ledger%rowtype;
  v_state_count bigint;
  v_ledger_count bigint;
  v_broken_links bigint;
  v_base jsonb;
begin
  select count(*) into v_state_count
  from public.shine_ai_witness_quorum_policy_state;

  select count(*) into v_ledger_count
  from public.shine_ai_witness_quorum_policy_ledger;

  if v_state_count=0 and v_ledger_count=0 then
    return jsonb_build_object('status','unbootstrapped');
  end if;

  if v_state_count<>1 or v_ledger_count<1 then
    return jsonb_build_object(
      'status','inconsistent',
      'reason_code','witness-quorum-policy-cardinality-mismatch'
    );
  end if;

  select *
  into v_state
  from public.shine_ai_witness_quorum_policy_state
  where singleton=true;

  select *
  into v_ledger
  from public.shine_ai_witness_quorum_policy_ledger
  order by generation desc,id desc
  limit 1;

  if v_ledger_count<>v_state.generation then
    return jsonb_build_object(
      'status','inconsistent',
      'reason_code','witness-quorum-policy-history-cardinality-mismatch'
    );
  end if;

  select count(*)
  into v_broken_links
  from (
    select
      generation,
      previous_policy_sha256,
      lag(policy_sha256) over(order by generation) as prior_sha,
      lag(generation) over(order by generation) as prior_generation
    from public.shine_ai_witness_quorum_policy_ledger
  ) x
  where
    (generation=1 and previous_policy_sha256 is not null)
    or
    (
      generation>1
      and (
        prior_generation is null
        or generation<>prior_generation+1
        or previous_policy_sha256 is distinct from prior_sha
      )
    );

  if v_broken_links<>0 then
    return jsonb_build_object(
      'status','inconsistent',
      'reason_code','witness-quorum-policy-history-chain-mismatch'
    );
  end if;

  if v_state.generation<>v_ledger.generation
     or v_state.minimum_witnesses<>v_ledger.minimum_witnesses
     or v_state.accepted_witness_ids<>v_ledger.accepted_witness_ids
     or v_state.previous_policy_sha256 is distinct from v_ledger.previous_policy_sha256
     or v_state.policy_sha256<>v_ledger.policy_sha256 then
    return jsonb_build_object(
      'status','inconsistent',
      'reason_code','witness-quorum-policy-high-water-mismatch'
    );
  end if;

  v_base := jsonb_build_object(
    'trust_state',jsonb_build_object(
      'trustStateVersion',1,
      'trustStateType','decision_trace_trust_state_witness_quorum_policy',
      'generation',v_state.generation,
      'minimumWitnesses',v_state.minimum_witnesses,
      'acceptedWitnessIds',to_jsonb(v_state.accepted_witness_ids),
      'previousPolicySha256',v_state.previous_policy_sha256,
      'policySha256',v_state.policy_sha256
    ),
    'acceptance',jsonb_build_object(
      'mode',v_ledger.acceptance_mode,
      'authorizingWitnessIds',
        case
          when v_ledger.authorizing_witness_ids is null then '[]'::jsonb
          else to_jsonb(v_ledger.authorizing_witness_ids)
        end,
      'authorizationCount',
        coalesce(cardinality(v_ledger.authorizing_witness_ids),0),
      'authorizationSha256',v_ledger.authorization_sha256
    ),
    'ledger_rows',v_ledger_count
  );

  if v_state.state_sha256 is null
     or v_state.storage_auth_key_id is null
     or v_state.storage_auth_tag is null then
    return v_base || jsonb_build_object(
      'status','unsealed',
      'reason_code','witness-quorum-policy-storage-authentication-missing'
    );
  end if;

  return v_base || jsonb_build_object(
    'status','trusted',
    'state_sha256',v_state.state_sha256,
    'storage_auth_key_id',v_state.storage_auth_key_id,
    'storage_auth_tag',v_state.storage_auth_tag
  );
end;
$$;

create or replace function public.shine_ai_witness_quorum_policy_advance_v3(
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
  v_snapshot jsonb;
  v_current jsonb;
  v_current_ids text[];
  v_current_minimum integer;
  v_sorted_next text[];
  v_sorted_authorizers text[];
  v_invalid_authorizers integer;
begin
  perform pg_advisory_xact_lock(
    hashtext('shine-ai-witness-quorum-policy-v3')
  );

  if p_expected_generation<1
     or p_next_generation<>p_expected_generation+1
     or p_expected_policy_sha256 !~ '^[a-f0-9]{64}$'
     or p_next_previous_policy_sha256<>p_expected_policy_sha256
     or p_next_policy_sha256 !~ '^[a-f0-9]{64}$'
     or p_next_minimum_witnesses<2
     or p_next_minimum_witnesses>4
     or cardinality(p_next_accepted_witness_ids)<2
     or cardinality(p_next_accepted_witness_ids)>4
     or p_next_minimum_witnesses>cardinality(p_next_accepted_witness_ids)
     or p_authorization_sha256 !~ '^[a-f0-9]{64}$'
     or p_state_sha256 !~ '^[a-f0-9]{64}$'
     or p_storage_auth_key_id !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
     or p_storage_auth_tag !~ '^[a-f0-9]{64}$' then
    raise exception 'invalid witness quorum policy transition';
  end if;

  select array_agg(x order by x)
  into v_sorted_next
  from unnest(p_next_accepted_witness_ids) x;

  if v_sorted_next is distinct from p_next_accepted_witness_ids
     or cardinality(p_next_accepted_witness_ids)
       <> (select count(distinct x) from unnest(p_next_accepted_witness_ids) x)
     or exists (
       select 1 from unnest(p_next_accepted_witness_ids) x
       where x !~ '^[a-z0-9][a-z0-9._-]{0,63}$'
     ) then
    raise exception 'invalid witness quorum policy membership';
  end if;

  v_snapshot := public.shine_ai_witness_quorum_policy_snapshot_v3();
  if v_snapshot->>'status'<>'trusted' then
    raise exception 'witness quorum policy storage inconsistent';
  end if;

  v_current := v_snapshot->'trust_state';
  if (v_current->>'generation')::integer<>p_expected_generation
     or v_current->>'policySha256'<>p_expected_policy_sha256 then
    raise exception 'witness quorum policy transition precondition mismatch';
  end if;

  select array_agg(value order by value)
  into v_current_ids
  from jsonb_array_elements_text(v_current->'acceptedWitnessIds') value;
  v_current_minimum := (v_current->>'minimumWitnesses')::integer;

  if p_next_minimum_witnesses=v_current_minimum
     and p_next_accepted_witness_ids=v_current_ids then
    raise exception 'witness quorum policy no-op transition';
  end if;

  if cardinality(p_authorizing_witness_ids)<v_current_minimum
     or cardinality(p_authorizing_witness_ids)>cardinality(v_current_ids) then
    raise exception 'insufficient previous-quorum authorizations';
  end if;

  select array_agg(x order by x)
  into v_sorted_authorizers
  from unnest(p_authorizing_witness_ids) x;

  if v_sorted_authorizers is distinct from p_authorizing_witness_ids
     or cardinality(p_authorizing_witness_ids)
       <> (select count(distinct x) from unnest(p_authorizing_witness_ids) x) then
    raise exception 'duplicate or unsorted previous-quorum authorizations';
  end if;

  select count(*)
  into v_invalid_authorizers
  from unnest(p_authorizing_witness_ids) x
  where not (x=any(v_current_ids));

  if v_invalid_authorizers<>0 then
    raise exception 'authorization from non-member witness';
  end if;

  update public.shine_ai_witness_quorum_policy_state
  set generation=p_next_generation,
      minimum_witnesses=p_next_minimum_witnesses,
      accepted_witness_ids=p_next_accepted_witness_ids,
      previous_policy_sha256=p_next_previous_policy_sha256,
      policy_sha256=p_next_policy_sha256,
      source='previous-quorum-transition',
      state_sha256=p_state_sha256,
      storage_auth_key_id=p_storage_auth_key_id,
      storage_auth_tag=p_storage_auth_tag,
      accepted_at=now(),
      updated_at=now()
  where singleton=true
    and generation=p_expected_generation
    and policy_sha256=p_expected_policy_sha256;

  if not found then
    raise exception 'witness quorum policy transition lost race';
  end if;

  insert into public.shine_ai_witness_quorum_policy_ledger(
    generation,
    minimum_witnesses,
    accepted_witness_ids,
    previous_policy_sha256,
    policy_sha256,
    acceptance_mode,
    authorizing_witness_ids,
    authorization_sha256,
    accepted_at
  ) values (
    p_next_generation,
    p_next_minimum_witnesses,
    p_next_accepted_witness_ids,
    p_next_previous_policy_sha256,
    p_next_policy_sha256,
    'previous-quorum-transition',
    p_authorizing_witness_ids,
    p_authorization_sha256,
    now()
  );

  return public.shine_ai_witness_quorum_policy_snapshot_v3();
end;
$$;

revoke all on function public.shine_ai_witness_quorum_policy_snapshot_v3()
  from public,anon,authenticated;
revoke all on function public.shine_ai_witness_quorum_policy_advance_v3(
  integer,text,integer,integer,text[],text,text,text[],text,text,text,text
) from public,anon,authenticated;

grant execute on function public.shine_ai_witness_quorum_policy_snapshot_v3()
  to service_role;
grant execute on function public.shine_ai_witness_quorum_policy_advance_v3(
  integer,text,integer,integer,text[],text,text,text[],text,text,text,text
) to service_role;
