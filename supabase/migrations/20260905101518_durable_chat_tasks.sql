-- Backend-only task journal. user_id identifies a browser capability, not an Auth user.
create table public.l_chat_tasks (
 request_id uuid primary key,
 user_id uuid not null,
 owner_hash text not null check (length(owner_hash)=64),
 input_hash text not null,
 request jsonb not null,
 status text not null default 'queued' check(status in ('queued','running','ready','failed','interrupted')),
 checkpoint text not null default 'queued',
 worker_id uuid,
 lease_until timestamptz,
 result jsonb,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now()
);
alter table public.l_chat_tasks enable row level security;
revoke all on public.l_chat_tasks from public, anon, authenticated;
grant select, insert, update, delete on public.l_chat_tasks to service_role;
create index l_chat_tasks_queue on public.l_chat_tasks(created_at) where status='queued';
create index l_chat_tasks_lease on public.l_chat_tasks(lease_until) where status='running';
create index l_chat_tasks_owner on public.l_chat_tasks(user_id, created_at desc);

create function public.l_task_submit(p_id uuid, p_user uuid, p_owner text, p_hash text, p_request jsonb)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare t public.l_chat_tasks;
begin
 insert into public.l_chat_tasks(request_id,user_id,owner_hash,input_hash,request)
 values(p_id,p_user,p_owner,p_hash,p_request) on conflict(request_id) do nothing;
 select * into t from public.l_chat_tasks where request_id=p_id;
 if t.owner_hash<>p_owner or t.user_id<>p_user then return jsonb_build_object('status','not_found'); end if;
 if t.input_hash<>p_hash then return jsonb_build_object('status','conflict'); end if;
 return jsonb_build_object('status',t.status,'request_id',t.request_id);
end $$;

create function public.l_task_claim(p_worker uuid)
returns setof public.l_chat_tasks language plpgsql security invoker set search_path='' as $$
begin
 -- Never replay work whose external effects may already have happened.
 update public.l_chat_tasks set status='interrupted', updated_at=now()
 where status='running' and lease_until < now();
 return query
 update public.l_chat_tasks set status='running', checkpoint='starting', worker_id=p_worker,
 lease_until=now()+interval '2 minutes', updated_at=now()
 where request_id=(select request_id from public.l_chat_tasks where status='queued'
 order by created_at for update skip locked limit 1)
 returning *;
end $$;

create function public.l_task_progress(p_id uuid, p_worker uuid, p_checkpoint text default null)
returns boolean language plpgsql security invoker set search_path='' as $$
begin
 update public.l_chat_tasks set lease_until=now()+interval '2 minutes',
 checkpoint=coalesce(p_checkpoint,checkpoint),updated_at=now()
 where request_id=p_id and worker_id=p_worker and status='running' and lease_until>=now();
 return found;
end $$;

create function public.l_task_finish(p_id uuid, p_worker uuid, p_status text, p_result jsonb)
returns boolean language plpgsql security invoker set search_path='' as $$
begin
 if p_status not in ('ready','failed') then raise exception 'Invalid terminal status'; end if;
 update public.l_chat_tasks set status=p_status, result=p_result, checkpoint=p_status, updated_at=now()
 where request_id=p_id and worker_id=p_worker and status='running' and lease_until>=now();
 return found;
end $$;

revoke all on function public.l_task_submit(uuid,uuid,text,text,jsonb) from public,anon,authenticated;
revoke all on function public.l_task_claim(uuid) from public,anon,authenticated;
revoke all on function public.l_task_progress(uuid,uuid,text) from public,anon,authenticated;
revoke all on function public.l_task_finish(uuid,uuid,text,jsonb) from public,anon,authenticated;
grant execute on function public.l_task_submit(uuid,uuid,text,text,jsonb) to service_role;
grant execute on function public.l_task_claim(uuid) to service_role;
grant execute on function public.l_task_progress(uuid,uuid,text) to service_role;
grant execute on function public.l_task_finish(uuid,uuid,text,jsonb) to service_role;
