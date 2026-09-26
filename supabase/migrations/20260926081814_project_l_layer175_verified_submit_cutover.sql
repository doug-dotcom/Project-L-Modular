create or replace function public.l_task_submit_verified(
    p_id uuid,
    p_user uuid,
    p_owner text,
    p_hash text,
    p_request jsonb,
    p_proof text
)
returns jsonb
language plpgsql
security invoker
set search_path=''
as $function$
declare
    t public.l_chat_tasks;
    message_text text;
    conversation_text text;
    expected_proof text;
    proof_bytes bytea;
begin
    if p_id is null
       or p_user is null
       or p_owner is null
       or length(p_owner) <> 64
       or p_owner !~ '^[0-9a-f]{64}$'
       or p_hash is null
       or p_hash !~ '^[0-9a-f]{64}$'
       or p_proof is null
       or p_proof !~ '^[0-9a-f]{64}$'
       or p_request is null
       or jsonb_typeof(p_request) <> 'object'
       or p_request->>'request_id' is distinct from p_id::text
       or jsonb_typeof(p_request->'message') is distinct from 'string'
       or (
            p_request ? 'conversation_id'
            and jsonb_typeof(p_request->'conversation_id') not in ('string','null')
       ) then
        return jsonb_build_object('status','invalid');
    end if;

    message_text := p_request->>'message';
    conversation_text := p_request->>'conversation_id';

    proof_bytes :=
        convert_to('layer175-submit-v1|', 'UTF8')
        || convert_to(
            'S' || octet_length(p_id::text)::text || ':' || p_id::text,
            'UTF8'
        )
        || case
            when conversation_text is null then convert_to('N', 'UTF8')
            else convert_to(
                'S' || octet_length(conversation_text)::text || ':' || conversation_text,
                'UTF8'
            )
           end
        || convert_to(
            'S' || octet_length(message_text)::text || ':' || message_text,
            'UTF8'
        );

    expected_proof := encode(
        extensions.digest(proof_bytes, 'sha256'),
        'hex'
    );

    if expected_proof <> p_proof then
        return jsonb_build_object('status','invalid');
    end if;

    insert into public.l_chat_tasks(
        request_id,user_id,owner_hash,input_hash,request
    )
    values(p_id,p_user,p_owner,p_hash,p_request)
    on conflict(request_id) do nothing;

    select * into t
      from public.l_chat_tasks
     where request_id=p_id;

    if t.owner_hash<>p_owner or t.user_id<>p_user then
        return jsonb_build_object('status','not_found');
    end if;

    if t.input_hash<>p_hash or t.request<>p_request then
        return jsonb_build_object('status','conflict');
    end if;

    return jsonb_build_object('status',t.status,'request_id',t.request_id);
end
$function$;

revoke execute on function public.l_task_submit_verified(uuid,uuid,text,text,jsonb,text)
from public, anon, authenticated;
grant execute on function public.l_task_submit_verified(uuid,uuid,text,text,jsonb,text)
to service_role;
revoke execute on function public.l_task_submit(uuid,uuid,text,text,jsonb)
from service_role;
comment on function public.l_task_submit(uuid,uuid,text,text,jsonb) is
  'Retired by Project L Layer 175 verified-submit cutover. Use l_task_submit_verified with an independently computed envelope proof.';
