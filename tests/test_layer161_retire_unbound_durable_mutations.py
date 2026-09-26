"""Layer 161 — retire every service-role path for unbound durable mutations."""
from pathlib import Path
from types import SimpleNamespace as NS

from core.cognition.durable_tasks import TaskRunner, TaskStore, request_hash

REQUEST_ID = "00000000-0000-4000-8000-000000000161"
WORKER_ID = "22222222-2222-4222-8222-222222222161"
CLAIM_TOKEN = "33333333-3333-4333-8333-333333333174"

class RpcClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return NS(execute=lambda: NS(data=True))


def request():
    return {"request_id": REQUEST_ID, "message": "Layer 161 fixture"}


def test_task_store_exposes_only_bound_mutation_methods():
    store = TaskStore(None)
    assert not hasattr(store, "progress")
    assert not hasattr(store, "finish")
    assert hasattr(store, "progress_bound")
    assert hasattr(store, "finish_bound")
    assert hasattr(store, "reject_bound")


def test_reject_bound_uses_exact_claim_tuple():
    client = RpcClient()
    store = TaskStore(client)
    req = request()
    digest = request_hash(req)
    payload = {
        "reply": (
            "This task stopped before execution because its saved request "
            "failed integrity verification. Please submit it again."
        ),
        "error": True,
    }

    assert store.reject_bound(
        REQUEST_ID, WORKER_ID, digest, req, payload, claim_token=CLAIM_TOKEN
    ) is True
    assert client.calls == [(
        "l_task_reject_claim_bound",
        {
            "p_id": REQUEST_ID,
            "p_worker": WORKER_ID,
            "p_claim_token": CLAIM_TOKEN,
            "p_hash": digest,
            "p_request": req,
            "p_result": payload,
        },
    )]


class RunnerStore:
    def __init__(self):
        self.rejected = []
        self.finished = []
        self.progressed = []

    def reject_bound(self, request_id, worker, input_hash, req, payload):
        self.rejected.append((request_id, worker, input_hash, req, payload))
        return True

    def progress_bound(self, *args, **kwargs):
        self.progressed.append((args, kwargs))
        return True

    def finish_bound(self, request_id, worker, input_hash, req, payload, status="ready"):
        self.finished.append((status, payload))
        return True


def test_invalid_claim_is_rejected_without_execution_or_unbound_write():
    store = RunnerStore()
    effects = []
    req = request()
    task = {
        "request_id": REQUEST_ID,
        "request": req,
        "input_hash": request_hash(req),
        "_request_integrity": {
            "version": "1.0",
            "status": "mismatch",
            "valid": False,
            "issues": ["request_hash_mismatch"],
            "request_id_bound": False,
        },
    }

    TaskRunner(
        store,
        lambda _: effects.append("executed") or {"reply": "wrong"},
    ).run_one(task, WORKER_ID)

    assert effects == []
    assert store.progressed == []
    assert store.finished == []
    assert len(store.rejected) == 1
    assert store.rejected[0][2] == task["input_hash"]
    assert store.rejected[0][3] == req
    assert store.rejected[0][4]["error"] is True


def test_missing_claim_marker_fails_closed_and_uses_exact_row_rejection():
    store = RunnerStore()
    effects = []
    req = request()
    task = {
        "request_id": REQUEST_ID,
        "request": req,
        "input_hash": request_hash(req),
    }

    TaskRunner(
        store,
        lambda _: effects.append("executed") or {"reply": "wrong"},
    ).run_one(task, WORKER_ID)

    assert effects == []
    assert store.finished == []
    assert len(store.rejected) == 1


def test_unbound_rpc_names_are_absent_from_runtime_mutation_calls():
    source = Path("core/cognition/durable_tasks.py").read_text(encoding="utf-8")
    assert "self.rpc('l_task_progress'," not in source
    assert "self.rpc('l_task_finish'," not in source
    assert "self.store.progress(" not in source
    assert "self.store.finish(" not in source
    assert "l_task_reject_claim_bound" in source


def test_layer161_migration_retires_service_role_legacy_mutations():
    source = Path(
        "supabase/migrations/"
        "20260925114145_project_l_layer161_retire_unbound_durable_mutations.sql"
    ).read_text(encoding="utf-8")

    assert "create function public.l_task_reject_bound" in source
    assert "security invoker" in source
    assert "set search_path=''" in source
    assert "and input_hash = p_hash" in source
    assert "and request = p_request" in source
    assert (
        "revoke execute on function public.l_task_progress(uuid,uuid,text)"
        in source
    )
    assert (
        "revoke execute on function public.l_task_finish(uuid,uuid,text,jsonb)"
        in source
    )
    assert "from service_role;" in source
    assert (
        "grant execute on function "
        "public.l_task_reject_bound(uuid,uuid,text,jsonb,jsonb)"
        in source
    )
