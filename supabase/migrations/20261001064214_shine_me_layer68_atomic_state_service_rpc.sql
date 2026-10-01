create or replace function public.shine_me_owner_state_apply_service_v1(
  p_owner_id text,
  p_expected_revision bigint,
  p_state jsonb
)
returns table (
  owner_id text,
  revision bigint,
  updated_at timestamptz
)
language sql
security invoker
set search_path = ''
as $$
  select *
  from private.shine_me_owner_state_apply_v1(
    p_owner_id,
    p_expected_revision,
    p_state
  );
$$;

revoke all on function public.shine_me_owner_state_apply_service_v1(text,bigint,jsonb)
  from public, anon, authenticated;
grant execute on function public.shine_me_owner_state_apply_service_v1(text,bigint,jsonb)
  to service_role;

comment on function public.shine_me_owner_state_apply_service_v1(text,bigint,jsonb) is
  'Shine Me Layer 68 service-only Data API wrapper for the private atomic owner-state writer. Security invoker; browser roles have no execute privilege.';
