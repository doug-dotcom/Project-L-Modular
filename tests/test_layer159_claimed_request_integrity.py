"""Layer 159 — verify claimed durable requests before any task execution."""
from types import SimpleNamespace as NS
from uuid import uuid4

from core.cognition.durable_tasks import TaskRunner, TaskStore, request_hash

REQUEST_ID = "00000000-0000-4000-8000-000000000159"


def req(**changes):
    value = {"request_id": REQUEST_ID, "message": "Claimed request"}
    value.update(changes)
    return value


class RpcClient:
    def __init__(self, rows):
        self.rows = rows

    def rpc(self, name, params):
        assert name == "l_task_claim"
        assert "p_worker" in params
        return NS(execute=lambda: NS(data=[dict(row) for row in self.rows]))


def claimed_row(request, input_hash):
    return {
        "request_id": REQUEST_ID,
        "request": request,
        "input_hash": input_hash,
        "status": "running",
        "checkpoint": "starting",
    }


def test_claim_marks_exact_request_verified_before_runner_sees_it():
    request = req()
    task = TaskStore(RpcClient([claimed_row(request, request_hash(request))])).claim(str(uuid4()))
    assert task["_request_integrity"] == {
        "version": "1.0",
        "status": "verified",
        "valid": True,
        "issues": [],
        "request_id_bound": True,
    }


def test_claim_marks_changed_request_invalid_before_runner_sees_it():
    original = req()
    changed = req(message="Changed after submission")
    task = TaskStore(RpcClient([claimed_row(changed, request_hash(original))])).claim(str(uuid4()))
    assert task["_request_integrity"]["valid"] is False
    assert "request_hash_mismatch" in task["_request_integrity"]["issues"]


def test_claim_marks_rebound_request_id_invalid():
    request = req(request_id="00000000-0000-4000-8000-000000000999")
    task = TaskStore(RpcClient([claimed_row(request, request_hash(request))])).claim(str(uuid4()))
    assert task["_request_integrity"]["valid"] is False
    assert "request_id_binding_mismatch" in task["_request_integrity"]["issues"]


def test_claim_marks_missing_hash_invalid():
    task = TaskStore(RpcClient([claimed_row(req(), None)])).claim(str(uuid4()))
    assert task["_request_integrity"]["valid"] is False
    assert "input_hash_shape_invalid" in task["_request_integrity"]["issues"]


class RunnerStore:
    def __init__(self):
        self.finished = []
        self.progressed = []
        self.rejected = []

    def progress_bound(self, request_id, worker, input_hash, request, stage=None):
        self.progressed.append(stage)
        return True

    def finish_bound(self, request_id, worker, input_hash, request, payload, status="ready"):
        self.finished.append((status, payload))
        return True

    def reject_bound(self, request_id, worker, input_hash, request, payload):
        self.rejected.append(payload)
        return True


def test_runner_refuses_invalid_claim_before_execute_or_checkpoint():
    store = RunnerStore()
    effects = []
    task = claimed_row(req(), request_hash(req()))
    task["_request_integrity"] = {
        "version": "1.0",
        "status": "mismatch",
        "valid": False,
        "issues": ["request_hash_mismatch"],
        "request_id_bound": False,
    }

    TaskRunner(store, lambda request: effects.append("executed") or {"reply": "bad"}).run_one(
        task, str(uuid4())
    )

    assert effects == []
    assert store.progressed == []
    assert store.finished == []
    assert len(store.rejected) == 1
    assert store.rejected[0]["error"] is True
    assert "before execution" in store.rejected[0]["reply"]


def test_runner_executes_verified_claim_once():
    store = RunnerStore()
    effects = []
    task = claimed_row(req(), request_hash(req()))
    task["_request_integrity"] = {
        "version": "1.0",
        "status": "verified",
        "valid": True,
        "issues": [],
        "request_id_bound": True,
    }

    TaskRunner(store, lambda request: effects.append(request["message"]) or {"reply": "done"}).run_one(
        task, str(uuid4())
    )

    assert effects == ["Claimed request"]
    assert store.finished == [("ready", {"reply": "done"})]


def test_runner_without_claim_integrity_marker_fails_closed():
    store = RunnerStore()
    effects = []
    request = {"request_id": REQUEST_ID, "message": "fixture"}
    TaskRunner(store, lambda request: effects.append("legacy") or {"reply": "done"}).run_one(
        {
            "request_id": REQUEST_ID,
            "request": request,
            "input_hash": request_hash(request),
        },
        str(uuid4()),
    )
    assert effects == []
    assert store.finished == []
    assert len(store.rejected) == 1
    assert store.rejected[0]["error"] is True
