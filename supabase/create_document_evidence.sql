-- Stage 7. Backend-owned provisioning configuration, not a human identity claim.
create table public.l_account_config (
 singleton boolean primary key default true check(singleton),
 allowed_email text not null,
 user_id uuid unique references auth.users(id)
);
alter table public.l_account_config enable row level security;
revoke all on public.l_account_config from public, anon, authenticated;
grant select, update on public.l_account_config to service_role;

create function public.l_account_session_valid(p_user uuid, p_session uuid)
returns boolean language plpgsql security definer set search_path='' as $$
declare candidate uuid;
begin
 -- Definer is required to check auth.sessions; only the backend may execute it.
 select u.id into candidate from auth.users u join auth.sessions s on s.user_id=u.id
 join public.l_account_config c on lower(c.allowed_email)=lower(u.email)
 where u.id=p_user and s.id=p_session and u.email_confirmed_at is not null
 and coalesce(u.is_anonymous,false)=false
 and (s.not_after is null or s.not_after>now())
 and (u.banned_until is null or u.banned_until<now());
 if candidate is null then return false; end if;
 update public.l_account_config set user_id=candidate where singleton and user_id is null;
 return exists(select 1 from public.l_account_config where user_id=candidate);
end $$;
revoke all on function public.l_account_session_valid(uuid,uuid) from public,anon,authenticated;
grant execute on function public.l_account_session_valid(uuid,uuid) to service_role;

create table public.l_evidence_documents (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id),
 filename text not null check(length(filename) between 1 and 180),
 mime_type text not null check(mime_type in ('application/pdf','image/jpeg','image/png','image/webp')),
 sha256 text not null check(sha256 ~ '^[a-f0-9]{64}$'),
 byte_size integer not null check(byte_size between 1 and 5242880),
 page_count integer not null check(page_count between 1 and 30),
 original_base64 text not null,
 pages jsonb not null check(jsonb_typeof(pages)='array' and jsonb_array_length(pages) between 1 and 30),
 created_at timestamptz not null default now(),
 unique(user_id,sha256),
 check(octet_length(decode(original_base64,'base64'))=byte_size),
 check(jsonb_array_length(pages)=page_count)
);
alter table public.l_evidence_documents enable row level security;
revoke all on public.l_evidence_documents from public,anon,authenticated;
-- Reads go through the backend's live-session check, not stale JWT-only Data API access.
create policy evidence_owner_read on public.l_evidence_documents for select to authenticated
 using (user_id=(select auth.uid()));
grant select,insert,delete on public.l_evidence_documents to service_role;
create index l_evidence_owner_created on public.l_evidence_documents(user_id,created_at desc);

create function public.l_evidence_save(p_user uuid,p_name text,p_mime text,p_original text,p_sha text,p_pages jsonb)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare d public.l_evidence_documents; raw bytea;
begin
 if not exists(select 1 from public.l_account_config where user_id=p_user) then
   raise exception 'Account not activated';
 end if;
 perform pg_advisory_xact_lock(hashtextextended(p_user::text,7));
 raw := decode(p_original,'base64');
 if encode(extensions.digest(raw,'sha256'),'hex')<>p_sha then raise exception 'Hash mismatch'; end if;
 select * into d from public.l_evidence_documents where user_id=p_user and sha256=p_sha;
 if found then return jsonb_build_object('id',d.id,'duplicate',true,'saved',true); end if;
 if (select count(*) from public.l_evidence_documents where user_id=p_user)>=20 then
   raise exception 'File limit reached';
 end if;
 if octet_length(p_pages::text)>1000000 then raise exception 'Extraction too large'; end if;
 insert into public.l_evidence_documents(user_id,filename,mime_type,sha256,byte_size,page_count,original_base64,pages)
 values(p_user,p_name,p_mime,p_sha,octet_length(raw),jsonb_array_length(p_pages),p_original,p_pages)
 returning * into d;
 return jsonb_build_object('id',d.id,'duplicate',false,'saved',true);
end $$;
revoke all on function public.l_evidence_save(uuid,text,text,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.l_evidence_save(uuid,text,text,text,text,jsonb) to service_role;
