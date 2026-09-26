"""Layer 173 — durable rejection is pre-execution only."""

import re
from pathlib import Path


def test_layer173_reject_rpc_is_token_bound_preexecution_only():
    source = Path(
        "supabase/migrations/"
        "20260926074116_project_l_layer173_harden_preexecution_reject.sql"
    ).read_text(encoding="utf-8")

    assert "create or replace function public.l_task_reject_bound" in source
    assert "security invoker" in source
    assert "set search_path=''" in source
    assert "and worker_id = p_worker" in source
    assert "and lease_until >= now()" in source
    assert "and input_hash = p_hash" in source
    assert "and request = p_request" in source
    assert "and claim_token is not null" in source
    assert "and checkpoint = 'starting'" in source
    assert "and result is null" in source
    assert "and action_receipt is null" in source


def test_layer173_reject_payload_cannot_fabricate_connected_action():
    source = Path(
        "supabase/migrations/"
        "20260926074116_project_l_layer173_harden_preexecution_reject.sql"
    ).read_text(encoding="utf-8")

    assert "p_result @> '{\"error\": true}'::jsonb" in source
    assert "jsonb_typeof(p_result->'reply') = 'string'" in source
    assert "p_result #> '{route,action_receipt}' is null" in source


def test_layer173_reject_rpc_remains_backend_only():
    source = Path(
        "supabase/migrations/"
        "20260926074116_project_l_layer173_harden_preexecution_reject.sql"
    ).read_text(encoding="utf-8")

    assert (
        "revoke execute on function "
        "public.l_task_reject_bound(uuid,uuid,text,jsonb,jsonb)"
        in source
    )
    assert "from public, anon, authenticated;" in source
    assert (
        "grant execute on function "
        "public.l_task_reject_bound(uuid,uuid,text,jsonb,jsonb)"
        in source
    )
    assert "to service_role;" in source


def test_runtime_only_invokes_reject_before_execution_setup():
    source = Path("core/cognition/durable_tasks.py").read_text(encoding="utf-8")

    assert source.count("self.store.reject_bound(") == 1
    reject_pos = source.index("self.store.reject_bound(")
    execution_setup_pos = source.index("done = threading.Event()", reject_pos)
    assert reject_pos < execution_setup_pos


def test_layer173_release_marker_is_continuous():
    source = Path("api/server.py").read_text(encoding="utf-8")
    layers = [
        int(value)
        for value in re.findall(r'release_layer"?\s*[:=]\s*(\d+)', source)
    ]
    assert len(layers) == 3
    assert len(set(layers)) == 1
    assert layers[0] >= 173
