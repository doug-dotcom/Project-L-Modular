begin;
insert into auth.users(id,email,email_confirmed_at,aud,role,is_anonymous) values
 ('07100000-0000-4000-8000-000000000001','l-stage7-owner@example.invalid',now(),'authenticated','authenticated',false),
 ('07100000-0000-4000-8000-000000000002','l-stage7-other@example.invalid',now(),'authenticated','authenticated',false);
insert into auth.sessions(id,user_id,created_at,updated_at) values
 ('07100000-0000-4000-8000-000000000011','07100000-0000-4000-8000-000000000001',now(),now()),
 ('07100000-0000-4000-8000-000000000012','07100000-0000-4000-8000-000000000002',now(),now());
insert into public.l_account_config(singleton,allowed_email,user_id) values(true,'l-stage7-owner@example.invalid',null)
on conflict(singleton) do update set allowed_email=excluded.allowed_email,user_id=null;
do $$
declare first jsonb; second jsonb; digest text;
begin
 if not public.l_account_session_valid('07100000-0000-4000-8000-000000000001','07100000-0000-4000-8000-000000000011') then raise exception 'Owner activation failed'; end if;
 if public.l_account_session_valid('07100000-0000-4000-8000-000000000002','07100000-0000-4000-8000-000000000012') then raise exception 'Other account allowed'; end if;
 if public.l_account_session_valid('07100000-0000-4000-8000-000000000001','07100000-0000-4000-8000-000000000012') then raise exception 'Other session allowed'; end if;
 digest:=encode(extensions.digest(convert_to('synthetic source','UTF8'),'sha256'),'hex');
 first:=public.l_evidence_save('07100000-0000-4000-8000-000000000001','synthetic.pdf','application/pdf','c3ludGhldGljIHNvdXJjZQ==',digest,'[{"page":1,"text":"synthetic source","kind":"pdf_text","truncated":false}]');
 second:=public.l_evidence_save('07100000-0000-4000-8000-000000000001','renamed.pdf','application/pdf','c3ludGhldGljIHNvdXJjZQ==',digest,'[{"page":1,"text":"synthetic source","kind":"pdf_text","truncated":false}]');
 if first->>'id'<>second->>'id' or second->>'duplicate'<>'true' then raise exception 'Duplicate original'; end if;
 begin
   perform public.l_evidence_save('07100000-0000-4000-8000-000000000002','other.pdf','application/pdf','c3ludGhldGljIHNvdXJjZQ==',digest,'[{}]');
   raise exception 'Other owner wrote file';
 exception when raise_exception then
   if SQLERRM <> 'Account not activated' then raise; end if;
 end;
 begin
   perform public.l_evidence_save('07100000-0000-4000-8000-000000000001','bad.pdf','application/pdf','c3ludGhldGljIHNvdXJjZQ==',repeat('0',64),'[{}]');
   raise exception 'Bad hash accepted';
 exception when raise_exception then
   if SQLERRM <> 'Hash mismatch' then raise; end if;
 end;
 if has_table_privilege('anon','public.l_evidence_documents','SELECT') or has_table_privilege('authenticated','public.l_evidence_documents','SELECT') then raise exception 'Direct API read bypass'; end if;
 if has_function_privilege('authenticated','public.l_evidence_save(uuid,text,text,text,text,jsonb)','EXECUTE') or has_function_privilege('anon','public.l_account_session_valid(uuid,uuid)','EXECUTE') then raise exception 'Public privileged function'; end if;
 delete from auth.sessions where id='07100000-0000-4000-8000-000000000011';
 if public.l_account_session_valid('07100000-0000-4000-8000-000000000001','07100000-0000-4000-8000-000000000011') then raise exception 'Revoked session allowed'; end if;
end $$;
rollback;
select 'Stage 7 transactional account, source integrity, deduplication and access tests passed' as result;
