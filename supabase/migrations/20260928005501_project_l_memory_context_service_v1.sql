create or replace function public.project_l_memory_context_service_v1(
  p_user uuid,
  p_terms text[],
  p_limit integer default 6,
  p_char_budget integer default 10000
)
returns jsonb
language sql
stable
security definer
set search_path = ''
set statement_timeout = '5s'
as $$
  select private.project_l_memory_context_v2(
    p_user,
    coalesce(p_terms, array[]::text[]),
    least(greatest(coalesce(p_limit,6),1),6),
    0,
    least(greatest(coalesce(p_char_budget,10000),2400),12000)
  );
$$;

revoke all on function public.project_l_memory_context_service_v1(
  uuid,text[],integer,integer
) from public, anon, authenticated;

grant execute on function public.project_l_memory_context_service_v1(
  uuid,text[],integer,integer
) to service_role;
