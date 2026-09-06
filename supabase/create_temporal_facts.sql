-- Stage 4. Backend-only, operator-curated facts; no automatic legacy backfill.
-- user_id is L's configured memory-owner scope, NOT a browser recovery identity.
create table public.l_fact_groups (
 user_id uuid not null,
 subject text not null check (length(subject) between 1 and 200),
 predicate text not null check (length(predicate) between 1 and 200),
 revision bigint not null default 0,
 timeline jsonb not null default '[]',
 updated_at timestamptz not null default now(),
 primary key(user_id,subject,predicate)
);
create table public.l_temporal_facts (
 id uuid primary key,
 user_id uuid not null,
 subject text not null,
 predicate text not null,
 claim text not null check(length(claim) between 1 and 4000),
 effective_from date not null,
 effective_to date,
 observed_at timestamptz not null,
 recorded_at timestamptz not null default now(),
 source_ref text not null check(length(source_ref) between 1 and 300),
 source_passage text not null check(length(source_passage) between 1 and 12000),
 source_role text not null check(source_role in ('user','assistant','document','operator')),
 status text not null default 'asserted' check(status in ('asserted','corrected')),
 supersedes uuid,
 change_kind text not null check(change_kind in ('assert','transition','correct')),
 request_payload jsonb not null,
 unique(user_id,id),
 foreign key(user_id,subject,predicate) references public.l_fact_groups(user_id,subject,predicate),
 foreign key(user_id,supersedes) references public.l_temporal_facts(user_id,id),
 check(effective_to is null or effective_to>effective_from),
 check(position(lower(claim) in lower(source_passage))>0)
);
create index l_temporal_facts_timeline on public.l_temporal_facts(user_id,subject,predicate,effective_from)
 where status='asserted';
create index l_temporal_facts_supersedes on public.l_temporal_facts(user_id,supersedes);
create table public.l_fact_observations (
 id uuid primary key,
 user_id uuid not null,
 fact_id uuid not null,
 observed_at timestamptz not null,
 source_ref text not null,
 source_passage text not null,
 recorded_at timestamptz not null default now(),
 foreign key(user_id,fact_id) references public.l_temporal_facts(user_id,id)
);
create index l_fact_observations_fact on public.l_fact_observations(user_id,fact_id);
create table public.l_fact_removal_requests (
 id uuid primary key,
 user_id uuid not null,
 fact_id uuid not null,
 inventory jsonb not null,
 status text not null default 'pending_review' check(status in ('pending_review','completed','declined')),
 created_at timestamptz not null default now(),
 foreign key(user_id,fact_id) references public.l_temporal_facts(user_id,id)
);
create index l_fact_removal_requests_fact on public.l_fact_removal_requests(user_id,fact_id);

alter table public.l_fact_groups enable row level security;
alter table public.l_temporal_facts enable row level security;
alter table public.l_fact_observations enable row level security;
alter table public.l_fact_removal_requests enable row level security;
revoke all on public.l_fact_groups, public.l_temporal_facts, public.l_fact_observations,
 public.l_fact_removal_requests from public, anon, authenticated;
grant select,insert,update,delete on public.l_fact_groups, public.l_temporal_facts,
 public.l_fact_observations, public.l_fact_removal_requests to service_role;

-- Row locks serialize corrections/transitions for a single owner and claim key.
-- Rebuild the dependent timeline in the SAME transaction; no stale summary window.
create function public.l_fact_write(p_user uuid, p_id uuid, p_subject text, p_predicate text,
 p_claim text, p_from date, p_to date, p_observed timestamptz, p_source text,
 p_passage text, p_role text, p_action text, p_replaces uuid default null)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare old public.l_temporal_facts; existing public.l_temporal_facts; rev bigint; req jsonb;
begin
 p_subject:=lower(trim(p_subject)); p_predicate:=lower(trim(p_predicate));
 req:=jsonb_build_object('user',p_user,'subject',p_subject,'predicate',p_predicate,
  'claim',p_claim,'from',p_from,'to',p_to,'observed',p_observed,'source',p_source,
  'passage',p_passage,'role',p_role,'action',p_action,'replaces',p_replaces);
 if p_action not in ('assert','transition','correct') or p_action is null then
  raise exception 'Invalid fact action';
 end if;
 if p_from is null or p_observed is null or p_from>(p_observed at time zone 'Australia/Brisbane')::date then
  raise exception 'Explicit effective and observation dates required; future claims are not facts';
 end if;
 if (p_action='assert')<>(p_replaces is null) then raise exception 'Replacement target required only for changes'; end if;
 insert into public.l_fact_groups(user_id,subject,predicate) values(p_user,p_subject,p_predicate)
 on conflict do nothing;
 perform 1 from public.l_fact_groups where user_id=p_user and subject=p_subject and predicate=p_predicate for update;
 select * into existing from public.l_temporal_facts where id=p_id;
 if found then
  if existing.request_payload=req then
   return jsonb_build_object('status','already_recorded','fact_id',p_id);
  end if;
  raise exception 'Request identifier already used';
 end if;
 if p_replaces is not null then
  select * into old from public.l_temporal_facts where id=p_replaces and user_id=p_user
   and subject=p_subject and predicate=p_predicate and status='asserted' for update;
  if not found then raise exception 'Replacement target is absent, corrected, or belongs to another claim'; end if;
  if p_action='transition' then
   if p_from<=old.effective_from or (old.effective_to is not null and p_from>=old.effective_to) then
    raise exception 'Transition must fall inside the prior validity interval';
   end if;
   if p_to is distinct from old.effective_to then raise exception 'Transition must preserve the prior end boundary'; end if;
   update public.l_temporal_facts set effective_to=p_from where id=old.id;
  else
   update public.l_temporal_facts set status='corrected' where id=old.id;
  end if;
 end if;
 if exists(select 1 from public.l_temporal_facts where user_id=p_user and subject=p_subject
  and predicate=p_predicate and status='asserted'
  and daterange(effective_from,effective_to,'[)') && daterange(p_from,p_to,'[)')) then
  raise exception 'Overlapping facts require an explicit correction or observation';
 end if;
 if (select count(*) from public.l_temporal_facts where user_id=p_user and subject=p_subject
  and predicate=p_predicate and status='asserted')>=128 then raise exception 'Timeline review required: 128 intervals'; end if;
 insert into public.l_temporal_facts(id,user_id,subject,predicate,claim,effective_from,effective_to,
  observed_at,source_ref,source_passage,source_role,supersedes,change_kind,request_payload)
 values(p_id,p_user,p_subject,p_predicate,p_claim,p_from,p_to,p_observed,p_source,p_passage,p_role,p_replaces,p_action,req);
 update public.l_fact_groups g set revision=revision+1,updated_at=now(),timeline=(
  select coalesce(jsonb_agg(jsonb_build_object('id',f.id,'claim',f.claim,
   'effective_from',f.effective_from,'effective_to',f.effective_to,'observed_at',f.observed_at,
   'recorded_at',f.recorded_at,'source_ref',f.source_ref,'source_passage',f.source_passage,
   'source_role',f.source_role,'supersedes',f.supersedes,'change_kind',f.change_kind)
   order by f.effective_from),'[]'::jsonb)
  from public.l_temporal_facts f where f.user_id=p_user and f.subject=p_subject
   and f.predicate=p_predicate and f.status='asserted')
 where g.user_id=p_user and g.subject=p_subject and g.predicate=p_predicate returning revision into rev;
 return jsonb_build_object('status','recorded','fact_id',p_id,'revision',rev,'summary_rebuilt',true);
end $$;

-- A newly observed mention never edits effective dates or increments fact revision.
create function public.l_fact_observe(p_user uuid,p_id uuid,p_fact uuid,p_observed timestamptz,p_source text,p_passage text)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare f public.l_temporal_facts; o public.l_fact_observations;
begin
 select * into f from public.l_temporal_facts where user_id=p_user and id=p_fact;
 if not found then raise exception 'Fact not found'; end if;
 if p_observed<f.observed_at or length(p_source)=0 or length(p_passage)=0 then raise exception 'Invalid observation'; end if;
 insert into public.l_fact_observations(id,user_id,fact_id,observed_at,source_ref,source_passage)
 values(p_id,p_user,p_fact,p_observed,p_source,p_passage) on conflict(id) do nothing;
 select * into o from public.l_fact_observations where id=p_id;
 if o.user_id<>p_user or o.fact_id<>p_fact or o.observed_at<>p_observed
  or o.source_ref<>p_source or o.source_passage<>p_passage then raise exception 'Observation identifier conflict'; end if;
 return jsonb_build_object('status','observed','fact_id',p_fact,'effective_dates_changed',false);
end $$;

-- One DB statement gives a consistent fact/dependency snapshot across workers.
create function public.l_fact_snapshot(p_user uuid,p_terms text[],p_from date default null,p_to date default null)
returns jsonb language sql stable security invoker set search_path='' as $$
 with matched as (
  select g.* from public.l_fact_groups g where g.user_id=p_user and exists(
   select 1 from unnest(p_terms[1:24]) t where length(t)>=2
    and position(lower(t) in (g.subject||' '||g.predicate))>0)
 ), bounded as (
  select g.user_id,g.subject,g.predicate,g.revision,g.updated_at,
   (select coalesce(jsonb_agg(f),'[]'::jsonb) from jsonb_array_elements(g.timeline) f
    where p_from is null or ((f->>'effective_from')::date<p_to
     and (f->>'effective_to' is null or (f->>'effective_to')::date>p_from))) as timeline
  from matched g order by subject,predicate limit 24)
 select jsonb_build_object('groups',coalesce((select jsonb_agg(to_jsonb(b)) from bounded b),'[]'::jsonb),
  'truncated',(select count(*)>24 from matched));
$$;

create function public.l_fact_freshness(p_user uuid,p_dependencies jsonb,p_terms text[])
returns jsonb language sql stable security invoker set search_path='' as $$
 select jsonb_build_object('status',case when exists(
  select 1 from jsonb_array_elements(p_dependencies) d left join public.l_fact_groups g
   on g.user_id=p_user and g.subject=d->>'subject' and g.predicate=d->>'predicate'
  where g.revision is null or g.revision<>(d->>'revision')::bigint
 ) or exists (
  select 1 from public.l_fact_groups g where g.user_id=p_user and exists(
   select 1 from unnest(p_terms[1:24]) t where length(t)>=2
    and position(lower(t) in (g.subject||' '||g.predicate))>0)
  and not exists(select 1 from jsonb_array_elements(p_dependencies) d
   where d->>'subject'=g.subject and d->>'predicate'=g.predicate)
 ) then 'superseded' else 'unchanged' end);
$$;

-- Removal is an explicit review workflow, not a side effect of correcting history.
-- No personal originals, historical facts, or saved receipts are deleted here.
create function public.l_fact_request_removal(p_user uuid,p_id uuid,p_fact uuid)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare f public.l_temporal_facts; inv jsonb;
begin
 select * into f from public.l_temporal_facts where user_id=p_user and id=p_fact;
 if not found then raise exception 'Fact not found'; end if;
 inv:=jsonb_build_object('source_ref',f.source_ref,'fact_id',f.id,
  'subject',f.subject,'predicate',f.predicate,'derived_timeline','l_fact_groups',
  'saved_answers',(select coalesce(jsonb_agg(t.request_id),'[]'::jsonb) from public.l_chat_tasks t
   where t.result->'cognition'->'temporal_memory'->>'user_id'=p_user::text
   and t.result->'cognition'->'temporal_memory'->'dependencies' @>
    jsonb_build_array(jsonb_build_object('subject',f.subject,'predicate',f.predicate))),
  'requires_review',jsonb_build_array('original source and legacy derivatives','fact and observation copies',
   'timeline and indexes','saved answers and client copies','backups and retention'));
 insert into public.l_fact_removal_requests(id,user_id,fact_id,inventory)
 values(p_id,p_user,p_fact,inv);
 return jsonb_build_object('status','pending_review','request_id',p_id,'inventory',inv,'deleted',false);
end $$;

revoke all on function public.l_fact_write(uuid,uuid,text,text,text,date,date,timestamptz,text,text,text,text,uuid),
 public.l_fact_observe(uuid,uuid,uuid,timestamptz,text,text),public.l_fact_snapshot(uuid,text[],date,date),
 public.l_fact_freshness(uuid,jsonb,text[]),public.l_fact_request_removal(uuid,uuid,uuid) from public,anon,authenticated;
grant execute on function public.l_fact_write(uuid,uuid,text,text,text,date,date,timestamptz,text,text,text,text,uuid),
 public.l_fact_observe(uuid,uuid,uuid,timestamptz,text,text),public.l_fact_snapshot(uuid,text[],date,date),
 public.l_fact_freshness(uuid,jsonb,text[]),public.l_fact_request_removal(uuid,uuid,uuid) to service_role;
