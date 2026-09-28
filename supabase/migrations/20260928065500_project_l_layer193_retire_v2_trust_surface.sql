-- Layer 193 post-cutover cleanup.
-- The v3 runtime is production healthy and persisted trust is authenticated.
-- Retire direct service-role access to the Layer 192 v2 trust surface.
-- v3 security-definer functions may continue to call v2 internals as owner.

revoke execute on function public.shine_ai_trace_trust_snapshot_v2()
    from service_role;
revoke execute on function public.shine_ai_trace_trust_bootstrap_v2(integer,text,jsonb)
    from service_role;
revoke execute on function public.shine_ai_trace_trust_advance_v2(integer,text,integer,text,jsonb,text,text,text)
    from service_role;
