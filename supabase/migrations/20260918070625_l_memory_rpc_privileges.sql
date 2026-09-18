-- The replacement search wrapper inherited public/default EXECUTE grants.
-- Restrict only Project L's wrapper; this database also hosts other apps.
revoke execute on function public.search_project_l_memory(text[], integer, integer)
  from public, anon, authenticated;
grant execute on function public.search_project_l_memory(text[], integer, integer)
  to service_role;
