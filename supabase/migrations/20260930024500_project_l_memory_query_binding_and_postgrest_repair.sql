-- Project L memory recovery hardening.
-- Query cohort identifiers are deterministic request/response bindings, not security tokens.
-- md5 is used only as a stable cohort identifier.

create or replace function public.project_l_memory_context_service_v2(
  p_user uuid,
  p_terms text[],
  p_query_key text,
  p_limit integer default 6,
  p_char_budget integer default 10000
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
set statement_timeout = '5s'
as $function$
declare
  v_terms text[] := coalesce(p_terms, array[]::text[]);
  v_query_key text := md5(array_to_string(coalesce(p_terms, array[]::text[]), chr(31)));
  v_payload jsonb;
begin
  if coalesce(p_query_key, '') <> v_query_key then
    raise exception 'Project L memory query cohort mismatch'
      using errcode = '22023';
  end if;

  v_payload := private.project_l_memory_context_v2(
    p_user,
    v_terms,
    least(greatest(coalesce(p_limit,6),1),6),
    0,
    least(greatest(coalesce(p_char_budget,10000),2400),12000)
  );

  if jsonb_typeof(v_payload) <> 'object' then
    raise exception 'Project L memory context returned invalid payload'
      using errcode = '22023';
  end if;

  return v_payload || jsonb_build_object(
    'queryKey', v_query_key,
    'queryContractVersion', '2'
  );
end;
$function$;

revoke all on function public.project_l_memory_context_service_v2(
  uuid,text[],text,integer,integer
) from public, anon, authenticated;
grant execute on function public.project_l_memory_context_service_v2(
  uuid,text[],text,integer,integer
) to service_role;

create or replace function public.search_project_l_memory_v2(
  p_terms text[],
  p_query_key text,
  p_raw_limit integer default 200,
  p_memory_limit integer default 200
)
returns jsonb
language plpgsql
stable
security invoker
set search_path = ''
set statement_timeout = '5s'
as $function$
declare
  v_terms text[] := coalesce(p_terms, array[]::text[]);
  v_query_key text := md5(array_to_string(coalesce(p_terms, array[]::text[]), chr(31)));
  v_payload jsonb;
begin
  if coalesce(p_query_key, '') <> v_query_key then
    raise exception 'Project L indexed recall query cohort mismatch'
      using errcode = '22023';
  end if;

  v_payload := public.search_project_l_memory(
    v_terms,
    least(greatest(coalesce(p_raw_limit,200),1),500),
    least(greatest(coalesce(p_memory_limit,200),1),500)
  );

  if jsonb_typeof(v_payload) <> 'object' then
    raise exception 'Project L indexed recall returned invalid payload'
      using errcode = '22023';
  end if;

  return v_payload || jsonb_build_object(
    'queryKey', v_query_key,
    'queryContractVersion', '2'
  );
end;
$function$;

revoke all on function public.search_project_l_memory_v2(
  text[],text,integer,integer
) from public, anon, authenticated;
grant execute on function public.search_project_l_memory_v2(
  text[],text,integer,integer
) to service_role;

-- Operational repair for the currently observed PostgREST schema-cache failure.
-- Supabase documents pg_notification_queue_usage() as the non-disruptive queue
-- refresh when PostgREST notifications become stuck.
select pg_notification_queue_usage();
notify pgrst, 'reload schema';
