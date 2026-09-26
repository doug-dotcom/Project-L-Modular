"""Layer 160 — bind durable checkpoints and result writes to the claimed request."""
from pathlib import Path
from types import SimpleNamespace as NS
from uuid import uuid4

from core.cognition.durable_tasks import CONTEXT, TaskRunner, TaskStore, checkpoint, request_hash

REQUEST_ID = "00000000-0000-4000-8000-000000000160"
WORKER_ID = "22222222-2222-4222-8222-222222222160"
CLAIM_TOKEN = "33333333-3333-4333-8333-333333333174"

def req():
    return {"request_id": REQUEST_ID, "message": "Bound request"}


class RpcClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return NS(execute=lambda: NS(data=True))


def test_task_store_bound_progress_passes_exact_claim_identity():
    client = RpcClient()
    store = TaskStore(client)
    request = req()
    digest = request_hash(request)

    assert store.progress_bound(REQUEST_ID, WORKER_ID, digest, request, "before_action", claim_token=CLAIM_TOKEN) is True
    name, params = client.calls[-1]
    assert name == "l_task_progress_claim_bound"
    assert params == {
        "p_id": REQUEST_ID,
        "p_worker": WORKER_ID,
        "p_claim_token": CLAIM_TOKEN,
        "p_hash": digest,
        "p_request": request,
        "p_checkpoint": "before_action",
    }


def test_task_store_bound_finish_passes_exact_claim_identity():
    client = RpcClient()
    store = TaskStore(client)
    request = req()
    digest = request_hash(request)
    payload = {"reply": "Bound result"}

    assert store.finish_bound(
        REQUEST_ID, WORKER_ID, digest, request, payload, status="ready", claim_token=CLAIM_TOKEN
    ) is True
    name, params = client.calls[-1]
    assert name == "l_task_finish_claim_bound"
    assert params == {
        "p_id": REQUEST_ID,
        "p_worker": WORKER_ID,
        "p_claim_token": CLAIM_TOKEN,
        "p_hash": digest,
        "p_request": request,
        "p_status": "ready",
        "p_result": payload,
    }


class BoundStore:
    def __init__(self, *, progress_ok=True, finish_ok=True):
        self.progress_ok = progress_ok
        self.finish_ok = finish_ok
        self.bound_progress = []
        self.bound_finish = []
        self.legacy_progress = []
        self.legacy_finish = []

    def progress(self, request_id, worker, stage=None):
        self.legacy_progress.append((request_id, worker, stage))
        return True

    def progress_bound(self, request_id, worker, input_hash, request, stage=None):
        self.bound_progress.append((request_id, worker, input_hash, request, stage))
        return self.progress_ok

    def finish(self, request_id, worker, payload, status="ready"):
        self.legacy_finish.append((request_id, worker, payload, status))
        return True

    def finish_bound(self, request_id, worker, input_hash, request, payload, status="ready"):
        self.bound_finish.append(
            (request_id, worker, input_hash, request, payload, status)
        )
        return self.finish_ok


def verified_task():
    request = req()
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


def test_checkpoint_on_verified_claim_uses_bound_progress_only():
    store = BoundStore()
    task = verified_task()
    CONTEXT.task = (
        store,
        REQUEST_ID,
        WORKER_ID,
        task["input_hash"],
        task["request"],
    )
    try:
        checkpoint("connected_actions")
    finally:
        CONTEXT.task = None

    assert len(store.bound_progress) == 1
    assert store.bound_progress[0][-1] == "connected_actions"
    assert store.legacy_progress == []


def test_verified_runner_persists_with_bound_finish_only():
    store = BoundStore()
    task = verified_task()
    effects = []

    TaskRunner(
        store,
        lambda request: effects.append(request["message"]) or {"reply": "done"},
    ).run_one(task, WORKER_ID)

    assert effects == ["Bound request"]
    assert len(store.bound_finish) == 1
    assert store.bound_finish[0][2] == task["input_hash"]
    assert store.bound_finish[0][3] == task["request"]
    assert store.bound_finish[0][4] == {"reply": "done"}
    assert store.bound_finish[0][5] == "ready"
    assert store.legacy_finish == []


def test_execution_cannot_mutate_the_claimed_binding_snapshot():
    store = BoundStore()
    task = verified_task()

    def mutate(request):
        request["message"] = "mutated inside execution"
        return {"reply": "done"}

    TaskRunner(store, mutate).run_one(task, WORKER_ID)

    assert task["request"]["message"] == "mutated inside execution"
    assert store.bound_finish[0][3]["message"] == "Bound request"


def test_verified_runner_does_not_fallback_to_unbound_finish_when_binding_is_lost():
    store = BoundStore(finish_ok=False)
    task = verified_task()

    TaskRunner(store, lambda request: {"reply": "must not fall back"}).run_one(
        task, WORKER_ID
    )

    assert len(store.bound_finish) == 1
    assert store.legacy_finish == []


def test_verified_execution_failure_uses_bound_failure_write():
    store = BoundStore()
    task = verified_task()

    def fail(_):
        raise RuntimeError("private synthetic detail")

    TaskRunner(store, fail).run_one(task, WORKER_ID)

    assert len(store.bound_finish) == 1
    assert store.bound_finish[0][5] == "failed"
    assert store.bound_finish[0][4]["error"] is True
    assert "private synthetic detail" not in str(store.bound_finish)
    assert store.legacy_finish == []


def test_layer160_migration_binds_both_progress_and_finish_to_request_and_hash():
    source = Path(
        "supabase/migrations/20260925112106_project_l_layer160_bound_durable_task_mutations.sql"
    ).read_text(encoding="utf-8")

    assert "create function public.l_task_progress_bound" in source
    assert "create function public.l_task_finish_bound" in source
    assert source.count("and input_hash = p_hash") == 2
    assert source.count("and request = p_request") == 2
    assert source.count("security invoker") == 2
    assert source.count("set search_path=''") == 2
    assert "revoke all on function public.l_task_progress_bound" in source
    assert "revoke all on function public.l_task_finish_bound" in source
    assert "to service_role;" in source
