create or replace function public.l_task_submit(
    p_id uuid,p_user uuid,p_owner text,p_hash text,p_request jsonb
)
returns jsonb language plpgsql security invoker set search_path=''
as $function$
declare t public.l_chat_tasks; expected_hash text;
begin
    if p_id is null or p_user is null or p_owner is null
       or length(p_owner) <> 64 or p_owner !~ '^[0-9a-f]{64}$'
       or p_hash is null or p_hash !~ '^[0-9a-f]{64}$'
       or p_request is null or jsonb_typeof(p_request) <> 'object'
       or p_request->>'request_id' is distinct from p_id::text then
        return jsonb_build_object('status','invalid');
    end if;
    expected_hash := encode(extensions.digest(convert_to(p_request::text,'UTF8'),'sha256'),'hex');
    if expected_hash <> p_hash then return jsonb_build_object('status','invalid'); end if;
    insert into public.l_chat_tasks(request_id,user_id,owner_hash,input_hash,request)
    values(p_id,p_user,p_owner,p_hash,p_request) on conflict(request_id) do nothing;
    select * into t from public.l_chat_tasks where request_id=p_id;
    if t.owner_hash<>p_owner or t.user_id<>p_user then return jsonb_build_object('status','not_found'); end if;
    if t.input_hash<>p_hash or t.request<>p_request then return jsonb_build_object('status','conflict'); end if;
    return jsonb_build_object('status',t.status,'request_id',t.request_id);
end
$function$;
revoke execute on function public.l_task_submit(uuid,uuid,text,text,jsonb) from public,anon,authenticated;
grant execute on function public.l_task_submit(uuid,uuid,text,text,jsonb) to service_role;
