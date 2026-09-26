"""Layer 170 — reconcile ambiguous terminal-save acknowledgements safely."""

import re
import threading
from types import SimpleNamespace

from core.cognition.durable_tasks import TaskRunner, TaskStore


REQUEST_ID = "10000000-0000-4000-8000-000000000170"
WORKER_ID = "20000000-0000-4000-8000-000000000170"
CLAIM_TOKEN = "33333333-3333-4333-8333-333333333174"
INPUT_HASH = "a" * 64
REQUEST = {
    "request_id": REQUEST_ID,
    "message": "layer 170 terminal persistence",
}
PAYLOAD = {
    "reply": "Layer 170 synthetic terminal payload.",
    "error": False,
}


class RpcClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=True))


class NoVerifyTaskStore(TaskStore):
    def _verify_finish_payload(self, request_id, payload):
        return None


class SequenceStore:
    def __init__(self, finish_results, confirm_results):
        self.finish_results = list(finish_results)
        self.confirm_results = list(confirm_results)
        self.finish_calls = []
        self.confirm_calls = []

    @staticmethod
    def _resolve(values):
        value = values.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

    def finish_bound(
        self, request_id, worker, input_hash, request, payload, status="ready"
    ):
        self.finish_calls.append(
            (request_id, worker, input_hash, request, payload, status)
        )
        return self._resolve(self.finish_results)

    def confirm_finish_bound(
        self, request_id, worker, input_hash, request, payload, status="ready"
    ):
        self.confirm_calls.append(
            (request_id, worker, input_hash, request, payload, status)
        )
        return self._resolve(self.confirm_results)


def persist(store, status="ready"):
    runner = TaskRunner(store, lambda _request: PAYLOAD)
    return runner._persist_terminal_bound(
        REQUEST_ID,
        WORKER_ID,
        INPUT_HASH,
        REQUEST,
        PAYLOAD,
        status,
        threading.Event(),
    )


def test_task_store_terminal_reconciliation_rpc_uses_exact_binding():
    client = RpcClient()
    store = NoVerifyTaskStore(client)

    assert store.confirm_finish_bound(
        REQUEST_ID,
        WORKER_ID,
        INPUT_HASH,
        REQUEST,
        PAYLOAD,
        status="ready",
        claim_token=CLAIM_TOKEN,
    ) is True

    assert client.calls == [
        (
            "l_task_confirm_finish_claim_bound",
            {
                "p_id": REQUEST_ID,
                "p_worker": WORKER_ID,
                "p_claim_token": CLAIM_TOKEN,
                "p_hash": INPUT_HASH,
                "p_request": REQUEST,
                "p_status": "ready",
                "p_result": PAYLOAD,
            },
        )
    ]


def test_lost_terminal_ack_is_accepted_when_exact_save_is_proven():
    store = SequenceStore(
        [ConnectionError("lost terminal acknowledgement")],
        [True],
    )

    assert persist(store) is True
    assert len(store.finish_calls) == 1
    assert len(store.confirm_calls) == 1


def test_uncommitted_ambiguous_terminal_write_retries_only_result_write():
    store = SequenceStore(
        [ConnectionError("lost acknowledgement"), True],
        [False],
    )

    assert persist(store) is True
    assert len(store.finish_calls) == 2
    assert len(store.confirm_calls) == 1


def test_prior_commit_can_be_proven_after_retry_returns_false():
    store = SequenceStore(
        [ConnectionError("lost acknowledgement"), False],
        [ConnectionError("reconciliation unavailable"), True],
    )

    assert persist(store) is True
    assert len(store.finish_calls) == 2
    assert len(store.confirm_calls) == 2


def test_definitive_terminal_rejection_is_not_retried_or_reconciled():
    store = SequenceStore([False], [])

    assert persist(store) is False
    assert len(store.finish_calls) == 1
    assert len(store.confirm_calls) == 0


def test_failed_terminal_status_uses_same_reconciliation_path():
    store = SequenceStore(
        [ConnectionError("lost failed-state acknowledgement")],
        [True],
    )

    assert persist(store, status="failed") is True
    assert store.finish_calls[0][-1] == "failed"
    assert store.confirm_calls[0][-1] == "failed"


def test_layer170_migration_is_read_only_bound_and_service_role_only():
    source = open(
        "supabase/migrations/20260926061352_project_l_layer170_reconcile_terminal_save_ack.sql",
        encoding="utf-8",
    ).read()

    assert "create or replace function public.l_task_confirm_finish_bound" in source
    assert "language sql" in source
    assert "security invoker" in source
    assert "set search_path=''" in source
    assert "stable" in source
    assert "p_status in ('ready', 'failed')" in source
    assert "worker_id = p_worker" in source
    assert "status = p_status" in source
    assert "checkpoint = p_status" in source
    assert "input_hash = p_hash" in source
    assert "request = p_request" in source
    assert "result = p_result" in source
    assert "p_result #> '{route,action_receipt}' = action_receipt" in source
    assert "from public, anon, authenticated" in source
    assert "to service_role;" in source
    assert "update public.l_chat_tasks" not in source.lower()
    assert "insert into public.l_chat_tasks" not in source.lower()


def test_layer170_release_marker_is_continuous():
    source = open("api/server.py", encoding="utf-8").read()
    layers = [
        int(value)
        for value in re.findall(r'release_layer"?\s*[:=]\s*(\d+)', source)
    ]
    assert len(layers) == 3
    assert len(set(layers)) == 1
    assert layers[0] >= 170
