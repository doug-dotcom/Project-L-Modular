"""Layer 172 — legacy unbound durable claim path is retired."""

import re


def test_runtime_has_no_legacy_claim_rpc_call():
    source = open("core/cognition/durable_tasks.py", encoding="utf-8").read()

    assert "rpc('l_task_claim'," not in source
    assert "rpc('l_task_claim_bound'," in source


def test_layer172_migration_retires_service_role_legacy_claim():
    source = open(
        "supabase/migrations/20260926072827_project_l_layer172_retire_legacy_claim.sql",
        encoding="utf-8",
    ).read()

    assert "revoke execute on function public.l_task_claim(uuid)" in source
    assert "from service_role;" in source
    assert "Retired by Project L Layer 172" in source
    assert "l_task_claim_bound(uuid, uuid)" in source


def test_durable_database_regression_suite_uses_bound_claims_only():
    source = open("supabase/tests/durable_tasks.sql", encoding="utf-8").read()

    assert "public.l_task_claim_bound(" in source
    assert "select * into t from public.l_task_claim(" not in source
    assert "perform public.l_task_claim(" not in source
    assert (
        "not has_function_privilege('service_role','public.l_task_claim(uuid)','execute')"
        in source
    )
    assert (
        "has_function_privilege('service_role','public.l_task_claim_bound(uuid,uuid)','execute')"
        in source
    )


def test_layer172_release_marker_is_continuous():
    source = open("api/server.py", encoding="utf-8").read()
    layers = [
        int(value)
        for value in re.findall(r'release_layer"?\s*[:=]\s*(\d+)', source)
    ]
    assert len(layers) == 3
    assert len(set(layers)) == 1
    assert layers[0] >= 172
