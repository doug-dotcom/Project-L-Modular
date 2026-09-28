-- Layer 209: expose only verified stable roster-head material.
-- The service role cannot read the underlying ledger/evidence tables directly.

create or replace function public.shine_ai_external_witness_roster_head_material_v1()
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
  v_count integer;
  v_min integer;
  v_max integer;
  v_bad integer;
  v_rows jsonb;
begin
  select count(*), min(generation), max(generation)
  into v_count, v_min, v_max
  from public.shine_ai_external_witness_roster_ledger;

  if v_count=0 then
    return jsonb_build_object(
      'status','empty',
      'reason_code','external-roster-head-history-empty'
    );
  end if;

  if v_min<>1 or v_max<>v_count then
    return jsonb_build_object(
      'status','invalid',
      'reason_code','external-roster-head-history-gap'
    );
  end if;

  select count(*) into v_bad
  from public.shine_ai_external_witness_roster_ledger l
  left join public.shine_ai_external_roster_transition_evidence e
    on e.generation=l.generation
  where
    (
      l.generation=1
      and (
        l.acceptance_mode<>'genesis-pin'
        or l.previous_policy_sha256 is not null
        or l.authorization_sha256 is not null
        or l.authorizing_witness_ids is not null
      )
    )
    or
    (
      l.generation>1
      and (
        l.acceptance_mode<>'previous-roster-quorum'
        or l.previous_policy_sha256 is null
        or l.authorization_sha256 is null
        or e.generation is null
        or e.previous_policy_sha256<>l.previous_policy_sha256
        or e.policy_sha256<>l.policy_sha256
        or e.authorization_sha256<>l.authorization_sha256
        or e.authorizing_witness_ids<>l.authorizing_witness_ids
      )
    );

  if v_bad<>0 then
    return jsonb_build_object(
      'status','invalid',
      'reason_code','external-roster-head-history-evidence-mismatch'
    );
  end if;

  select jsonb_agg(
    jsonb_build_object(
      'sequence',l.generation,
      'generation',l.generation,
      'previousPolicySha256',l.previous_policy_sha256,
      'policySha256',l.policy_sha256,
      'stateSha256',l.state_sha256
    )
    order by l.generation
  )
  into v_rows
  from public.shine_ai_external_witness_roster_ledger l;

  return jsonb_build_object(
    'status','verified',
    'historyVersion',1,
    'sequence',v_max,
    'generation',v_max,
    'rows',v_rows
  );
end;
$$;

revoke all on function
  public.shine_ai_external_witness_roster_head_material_v1()
  from public, anon, authenticated;
grant execute on function
  public.shine_ai_external_witness_roster_head_material_v1()
  to service_role;
