create or replace function public.l_task_confirm_submit(
    p_id uuid,
    p_user uuid,
    p_owner text,
    p_hash text,
    p_request jsonb
)
returns jsonb
language sql
security invoker
set search_path=''
stable
as $function$
    select coalesce(
        (
            select jsonb_build_object(
                'status', status,
                'request_id', request_id
            )
            from public.l_chat_tasks
            where request_id = p_id
              and user_id = p_user
              and owner_hash = p_owner
              and input_hash = p_hash
              and request = p_request
            limit 1
        ),
        jsonb_build_object('status', 'not_found')
    );
$function$;

revoke execute on function public.l_task_confirm_submit(uuid,uuid,text,text,jsonb)
from public, anon, authenticated;

grant execute on function public.l_task_confirm_submit(uuid,uuid,text,text,jsonb)
to service_role;
