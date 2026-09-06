-- Synthetic acceptance only. Fixture data rolls back; no model or private export.
begin;
do $test$
declare
  key text := 'stagefive' || replace(gen_random_uuid()::text, '-', '');
  payload jsonb;
  raw_id bigint;
  episode_id bigint;
  t timestamptz;
begin
  payload := public.l_recall_period('2026-03-01', '2026-08-31', array[key], 4);
  assert jsonb_array_length(payload->'months') = 6, 'six month windows';
  assert not exists (select 1 from jsonb_array_elements(payload->'months') m
                     where jsonb_array_length(m->'rows') <> 0), 'initial empty search';
  t := clock_timestamp();
  insert into public.raw_catchall(role, content, source, created_at)
    values('user', key || ' Synthetic recovery milestone. Recalled in August; happened in March.',
           'stage5_synthetic_test', '2026-08-15T12:00:00Z') returning id into raw_id;
  insert into public.episodic_memories(event_date, summary, source_reference, confidence)
    values('2026-03-10', key || ' Synthetic recovery milestone on 10 March.', raw_id, 1)
    returning id into episode_id;
  payload := public.l_recall_period('2026-03-01', '2026-08-31', array[key], 4);
  assert payload #>> '{months,0,rows,0,date_basis}' = 'event_date', 'event not recording date';
  assert payload #>> '{months,0,rows,0,source}' = 'episodic_memories:' || episode_id, 'traceable episode';
  assert payload #>> '{months,5,rows,0,date_basis}' = 'recorded_at', 'later mention remains recording';
  assert jsonb_array_length(payload #> '{months,2,rows}') = 0, 'empty month not invented';
  assert (payload #>> '{months,0,rows,0,raw_id}')::bigint = raw_id, 'raw source retained';
  assert exists(select 1 from public.raw_catchall where id=raw_id and content like key || '%'), 'full raw preserved';
  raise notice 'Stage 5 synthetic insert-to-search transaction latency ms: %',
    extract(epoch from clock_timestamp()-t)*1000;
  -- Brisbane midnight belongs to June, although UTC is still May.
  insert into public.raw_catchall(role, content, source, created_at)
    values('user', key || ' Brisbane boundary.', 'stage5_synthetic_test', '2026-05-31T14:01:00Z');
  payload := public.l_recall_period('2026-06-01', '2026-06-30', array[key], 4);
  assert payload #>> '{months,0,rows,0,date}' = '2026-06-01', 'Brisbane day';
  assert not has_function_privilege('anon','public.l_recall_period(date,date,text[],integer)','execute');
  assert not has_function_privilege('authenticated','public.l_recall_period(date,date,text[],integer)','execute');
  assert has_function_privilege('service_role','public.l_recall_period(date,date,text[],integer)','execute');
  begin
    perform public.l_recall_period('2024-01-01','2026-01-01',array[key],4);
    raise exception 'oversized period accepted';
  exception when raise_exception then
    assert sqlerrm = 'ordered period of at most one year required';
  end;
end;
$test$;
select 'Stage 5 SQL acceptance passed; synthetic fixtures rolled back' as result;
rollback;
