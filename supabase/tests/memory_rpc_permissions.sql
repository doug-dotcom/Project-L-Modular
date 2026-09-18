-- Read-only production acceptance: run after any memory RPC migration.
begin read only;
do $test$
declare
  signature text;
  fn regprocedure;
begin
  foreach signature in array array[
    'public.search_project_l_memory(text[],integer,integer)',
    'public.search_project_l_memory_base(text[],integer,integer)',
    'public.l_recall_period(date,date,text[],integer)',
    'public.project_l_candidate_row(jsonb,text,text,text,tsquery)',
    'public.restore_project_l_memory_quarantine(text,text,text)'
  ] loop
    fn := to_regprocedure(signature);
    assert fn is not null, 'Missing memory RPC: ' || signature;
    assert not has_function_privilege('anon', fn, 'execute'), 'Anonymous access: ' || signature;
    assert not has_function_privilege('authenticated', fn, 'execute'), 'Authenticated access: ' || signature;
    assert has_function_privilege('service_role', fn, 'execute'), 'Service access missing: ' || signature;
    assert not exists (
      select 1 from pg_proc p,
        lateral aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) a
      where p.oid = fn and a.grantee = 0 and a.privilege_type = 'EXECUTE'
    ), 'PUBLIC access: ' || signature;
    assert exists (
      select 1 from pg_proc where oid = fn and not prosecdef
        and 'search_path=""' = any(proconfig)
    ), 'Invoker security/fixed search path required: ' || signature;
  end loop;
end;
$test$;
select 'Memory RPC permissions: all five service-role-only checks passed' as result;
rollback;
