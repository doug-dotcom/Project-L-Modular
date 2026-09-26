"""Layer 174 — every post-claim mutation carries the one-shot claim token."""

import re
from types import SimpleNamespace

import pytest

from core.cognition.durable_tasks import DurableTaskBindingError, TaskStore

WORKER_ID = "20000000-0000-4000-8000-000000001741"
CLAIM_TOKEN = "30000000-0000-4000-8000-000000001741"
REQUEST_ID = "10000000-0000-4000-8000-000000001741"
REQUEST = {"request_id": REQUEST_ID, "message": "layer 174"}
HASH = "a" * 64

class RpcClient:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []
    def rpc(self, name, params):
        self.calls.append((name, params))
        data = self.rows if name == "l_task_claim_bound" else True
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=data))

class NoVerifyTaskStore(TaskStore):
    def _verify_finish_payload(self, request_id, payload):
        return None

def claimed_row(token=CLAIM_TOKEN):
    return {
        "request_id": REQUEST_ID,
        "request": REQUEST,
        "input_hash": HASH,
        "status": "running",
        "checkpoint": "starting",
        "claim_token": token,
    }

def test_claim_response_token_mismatch_fails_closed():
    client = RpcClient([claimed_row("30000000-0000-4000-8000-000000001799")])
    with pytest.raises(DurableTaskBindingError, match="token mismatch"):
        TaskStore(client).claim(WORKER_ID, claim_token=CLAIM_TOKEN)

def test_claim_token_is_remembered_and_used_by_progress_rpc():
    client = RpcClient([claimed_row()])
    store = TaskStore(client)
    store.claim(WORKER_ID, claim_token=CLAIM_TOKEN)
    assert store.progress_bound(REQUEST_ID, WORKER_ID, HASH, REQUEST, "checkpoint") is True
    name, params = client.calls[-1]
    assert name == "l_task_progress_claim_bound"
    assert params["p_claim_token"] == CLAIM_TOKEN

def test_missing_claim_token_binding_blocks_mutation_before_rpc():
    client = RpcClient()
    store = TaskStore(client)
    with pytest.raises(DurableTaskBindingError, match="claim token"):
        store.progress_bound(REQUEST_ID, WORKER_ID, HASH, REQUEST, "checkpoint")
    assert client.calls == []

def test_terminal_success_clears_process_local_claim_token():
    client = RpcClient([claimed_row()])
    store = NoVerifyTaskStore(client)
    store.claim(WORKER_ID, claim_token=CLAIM_TOKEN)
    assert store.finish_bound(REQUEST_ID, WORKER_ID, HASH, REQUEST, {"reply": "done"}) is True
    with pytest.raises(DurableTaskBindingError, match="claim token"):
        store.progress_bound(REQUEST_ID, WORKER_ID, HASH, REQUEST, "too_late")

def test_layer174_runtime_rpc_names_are_claim_token_bound():
    source = open("core/cognition/durable_tasks.py", encoding="utf-8").read()
    for name in [
        "l_task_progress_claim_bound",
        "l_task_record_action_claim_bound",
        "l_task_confirm_action_claim_bound",
        "l_task_finish_claim_bound",
        "l_task_confirm_finish_claim_bound",
        "l_task_reject_claim_bound",
    ]:
        assert name in source

def test_layer174_foundation_migration_binds_every_rpc_to_claim_token():
    source = open(
        "supabase/migrations/20260926075023_project_l_layer174_claim_token_mutation_spine.sql",
        encoding="utf-8",
    ).read()
    assert source.count("claim_token=p_claim_token") >= 6
    assert source.count("p_claim_token is not null") >= 6
    assert source.count("security invoker") >= 6
    assert "to service_role;" in source

def test_layer174_release_marker_is_continuous():
    source = open("api/server.py", encoding="utf-8").read()
    layers = [int(v) for v in re.findall(r'release_layer"?\s*[:=]\s*(\d+)', source)]
    assert len(layers) == 3
    assert len(set(layers)) == 1
    assert layers[0] >= 174
