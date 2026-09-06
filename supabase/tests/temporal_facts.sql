-- Run as backend operator. All synthetic rows are rolled back, including on failure.
begin;
do $$
declare u uuid:=gen_random_uuid(); other_owner uuid:=gen_random_uuid();
 old_id uuid:=gen_random_uuid(); live_id uuid:=gen_random_uuid(); correction_id uuid:=gen_random_uuid();
 unrelated_id uuid:=gen_random_uuid(); deps jsonb; snap jsonb; before_unrelated jsonb; result jsonb;
begin
 perform public.l_fact_write(u,old_id,'project cedar','status','prototype','2026-06-01',null,
  '2026-06-01T01:00:00+10:00','fixture:old','Project Cedar was a prototype in June.','document','assert');
 perform public.l_fact_write(u,live_id,'project cedar','status','live','2026-07-01',null,
  '2026-07-01T12:00:00Z','fixture:live','Project Cedar is live from July.','document','transition',old_id);
 perform public.l_fact_write(u,unrelated_id,'project birch','colour','green','2026-06-01',null,
  '2026-06-01T12:00:00Z','fixture:colour','Project Birch is green.','document','assert');
 before_unrelated:=public.l_fact_snapshot(u,array['birch']);
 snap:=public.l_fact_snapshot(u,array['cedar']);
 select jsonb_agg(jsonb_build_object('subject',g->>'subject','predicate',g->>'predicate','revision',g->'revision'))
  into deps from jsonb_array_elements(snap->'groups') g;
 assert (select claim='live' from public.l_temporal_facts where user_id=u and status='asserted'
  and daterange(effective_from,effective_to,'[)') @> date '2026-09-06' and subject='project cedar');
 assert (select claim='prototype' from public.l_temporal_facts where user_id=u and status='asserted'
  and daterange(effective_from,effective_to,'[)') @> date '2026-06-15' and subject='project cedar');
 perform public.l_fact_observe(u,gen_random_uuid(),old_id,'2026-09-05T12:00:00Z',
  'fixture:recent','Today I discussed the prototype status from June.');
 assert public.l_fact_snapshot(u,array['cedar'])=snap, 'Recent observation changed effective-time summary';
 assert public.l_fact_freshness(u,deps,array['cedar'])->>'status'='unchanged';
 perform public.l_fact_write(u,correction_id,'project cedar','status','pilot','2026-07-01',null,
  '2026-09-06T12:00:00Z','fixture:correction','Correction: Project Cedar has been a pilot since July, not live.',
  'document','correct',live_id);
 assert (select status='corrected' from public.l_temporal_facts where id=live_id);
 assert (select status='asserted' and effective_to='2026-07-01' from public.l_temporal_facts where id=old_id);
 assert public.l_fact_freshness(u,deps,array['cedar'])->>'status'='superseded';
 assert public.l_fact_snapshot(u,array['birch'])=before_unrelated, 'Unrelated summary changed';
 assert public.l_fact_snapshot(u,array['cedar'])->'groups'->0->'timeline'->1->>'claim'='pilot';
 assert public.l_fact_snapshot(other_owner,array['cedar'])->'groups'='[]'::jsonb;
 assert public.l_fact_freshness(u,'[]',array['cedar'])->>'status'='superseded', 'Negative cache not invalidated';
 assert public.l_fact_freshness(u,'[]',array['unknown'])->>'status'='unchanged';
 -- Same id and identical original request is idempotent even after its validity was closed.
 result:=public.l_fact_write(u,old_id,'project cedar','status','prototype','2026-06-01',null,
  '2026-06-01T01:00:00+10:00','fixture:old','Project Cedar was a prototype in June.','document','assert');
 assert result->>'status'='already_recorded';
 begin
  perform public.l_fact_write(u,old_id,'project cedar','status','prototype','2026-06-01','2026-06-20',
   '2026-06-01T01:00:00+10:00','fixture:old','Project Cedar was a prototype in June.','document','assert');
  raise exception 'TEST: conflicting id accepted';
 exception when others then
  if sqlerrm='TEST: conflicting id accepted' then raise; end if;
 end;
 begin
  perform public.l_fact_write(other_owner,gen_random_uuid(),'project cedar','status','broken','2026-07-01',null,
   '2026-09-06T12:00:00Z','fixture:attack','broken','document','correct',correction_id);
  raise exception 'TEST: cross-owner correction accepted';
 exception when others then
  if sqlerrm='TEST: cross-owner correction accepted' then raise; end if;
 end;
 begin
  perform public.l_fact_write(u,gen_random_uuid(),'project cedar','status','duplicate','2026-07-01',null,
   '2026-09-06T12:00:00Z','fixture:duplicate','duplicate','document','assert');
  raise exception 'TEST: overlapping assertion accepted';
 exception when others then
  if sqlerrm='TEST: overlapping assertion accepted' then raise; end if;
 end;
 result:=public.l_fact_request_removal(u,gen_random_uuid(),correction_id);
 assert result->>'status'='pending_review' and result->>'deleted'='false';
 assert exists(select 1 from public.l_temporal_facts where id=correction_id), 'Removal request deleted history';
 assert not has_table_privilege('anon','public.l_temporal_facts','SELECT');
 assert not has_table_privilege('authenticated','public.l_fact_groups','UPDATE');
 assert not has_function_privilege('anon',
  'public.l_fact_write(uuid,uuid,text,text,text,date,date,timestamptz,text,text,text,text,uuid)','EXECUTE');
 assert not has_function_privilege('authenticated','public.l_fact_snapshot(uuid,text[],date,date)','EXECUTE');
end $$;
select 'stage4_sql_acceptance_passed' as result;
rollback;
