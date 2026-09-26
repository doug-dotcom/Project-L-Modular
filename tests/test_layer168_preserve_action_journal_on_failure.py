"""Layer 168 — terminal failures preserve the exact durable action journal."""

import re
from types import SimpleNamespace
from uuid import uuid4

from core.cognition.action_receipt import build_action_receipt
from core.cognition.durable_tasks import (
    CONTEXT,
    TaskRunner,
    TaskStore,
    record_current_action_receipt,
    request_hash,
)


REQUEST_ID = "10000000-0000-4000-8000-000000000168"
CLAIM_TOKEN = "30000000-0000-4000-8000-000000000168"


def task():
    request = {
        "request_id": REQUEST_ID,
        "message": "add to my tasks: call electrician",
    }
    return {
        "request_id": REQUEST_ID,
        "request": request,
        "input_hash": request_hash(request),
        "_request_integrity": {
            "version": "1.0",
            "status": "verified",
            "valid": True,
            "issues": [],
            "request_id_bound": True,
        },
    }


def receipt():
    return build_action_receipt(
        request_id=REQUEST_ID,
        capability="google_tasks",
        action="create",
        resource_id="google-task-168",
        subject="call electrician",
    )


def run_bound(store, execute):
    worker = str(uuid4())
    store._remember_claim_token(worker, CLAIM_TOKEN)
    TaskRunner(store, execute, heartbeat_seconds=60).run_one(task(), worker)


class RpcClient:
    def __init__(self, finish_result=True):
        self.calls = []
        self.finish_result = finish_result

    def rpc(self, name, params):
        self.calls.append((name, params))
        data = self.finish_result if name == "l_task_finish_claim_bound" else True
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=data))


def test_journaled_action_then_exception_persists_matching_failed_result():
    client = RpcClient()
    store = TaskStore(client)
    action_receipt = receipt()

    def execute(_request):
        assert record_current_action_receipt(action_receipt) is True
        raise RuntimeError("synthetic post-action failure")

    run_bound(store, execute)

    names = [name for name, _params in client.calls]
    assert names == ["l_task_record_action_claim_bound", "l_task_finish_claim_bound"]

    journal_params = client.calls[0][1]
    finish_params = client.calls[1][1]
    assert finish_params["p_status"] == "failed"
    assert finish_params["p_result"]["error"] is True
    assert finish_params["p_result"]["route"]["status"] == "error"
    assert (
        finish_params["p_result"]["route"]["action_receipt"]
        == journal_params["p_receipt"]
    )
    assert (
        finish_params["p_result"]["route"]["action_receipt_verification"]["valid"]
        is True
    )


def test_failure_before_any_action_does_not_invent_action_receipt():
    client = RpcClient()
    store = TaskStore(client)

    def execute(_request):
        raise RuntimeError("failure before action")

    run_bound(store, execute)

    finish_calls = [
        params for name, params in client.calls if name == "l_task_finish_claim_bound"
    ]
    assert len(finish_calls) == 1
    payload = finish_calls[0]["p_result"]
    assert finish_calls[0]["p_status"] == "failed"
    assert "route" not in payload


def test_successfully_journaled_receipt_is_frozen_against_caller_mutation():
    client = RpcClient()
    store = TaskStore(client)
    original = receipt()

    def execute(_request):
        assert record_current_action_receipt(original) is True
        original["resource_id"] = "mutated-after-journal"
        raise RuntimeError("synthetic failure after mutation")

    run_bound(store, execute)

    journal = next(
        params["p_receipt"]
        for name, params in client.calls
        if name == "l_task_record_action_claim_bound"
    )
    failure = next(
        params["p_result"]
        for name, params in client.calls
        if name == "l_task_finish_claim_bound"
    )
    assert journal["resource_id"] == "google-task-168"
    assert failure["route"]["action_receipt"]["resource_id"] == "google-task-168"


def test_runner_clears_process_local_journal_after_task():
    client = RpcClient()
    store = TaskStore(client)

    def execute(_request):
        record_current_action_receipt(receipt())
        raise RuntimeError("synthetic failure")

    run_bound(store, execute)

    assert getattr(CONTEXT, "task", None) is None
    assert getattr(CONTEXT, "action_receipt", None) is None


def test_rejected_terminal_failure_is_not_mistaken_for_persisted():
    client = RpcClient(finish_result=False)
    store = TaskStore(client)

    def execute(_request):
        record_current_action_receipt(receipt())
        raise RuntimeError("synthetic failure")

    run_bound(store, execute)

    finish_calls = [
        params for name, params in client.calls if name == "l_task_finish_claim_bound"
    ]
    assert len(finish_calls) == 1
    assert finish_calls[0]["p_status"] == "failed"


def test_layer168_release_marker_is_continuous():
    source = open("api/server.py", encoding="utf-8").read()
    layers = [
        int(value)
        for value in re.findall(r'release_layer"?\s*[:=]\s*(\d+)', source)
    ]
    assert len(layers) == 3
    assert len(set(layers)) == 1
    assert layers[0] >= 168
