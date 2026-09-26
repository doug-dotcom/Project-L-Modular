"""Layer 169 — reconcile ambiguous journal acknowledgements without replay."""

import re
import threading
from types import SimpleNamespace

import pytest

from core.cognition.action_receipt import build_action_receipt
from core.cognition.durable_tasks import (
    CONTEXT,
    DurableTaskBindingError,
    TaskStore,
    record_current_action_receipt,
    request_hash,
)


REQUEST_ID = "10000000-0000-4000-8000-000000000169"
WORKER_ID = "20000000-0000-4000-8000-000000000169"


def request():
    return {
        "request_id": REQUEST_ID,
        "message": "add to my tasks: call electrician",
    }


def receipt():
    return build_action_receipt(
        request_id=REQUEST_ID,
        capability="google_tasks",
        action="create",
        resource_id="google-task-169",
        subject="call electrician",
    )


def bind(store):
    req = request()
    CONTEXT.task = (
        store,
        REQUEST_ID,
        WORKER_ID,
        request_hash(req),
        req,
        threading.Event(),
    )
    CONTEXT.action_receipt = None


class RpcClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=True))


class AmbiguousStore:
    def __init__(self, reconcile=True, reconcile_error=None):
        self.reconcile = reconcile
        self.reconcile_error = reconcile_error
        self.record_calls = []
        self.confirm_calls = []

    def record_action_bound(
        self, request_id, worker, input_hash, claimed_request, action_receipt
    ):
        self.record_calls.append(
            (request_id, worker, input_hash, claimed_request, action_receipt)
        )
        raise ConnectionError("synthetic lost acknowledgement")

    def confirm_action_bound(
        self, request_id, worker, input_hash, claimed_request, action_receipt
    ):
        self.confirm_calls.append(
            (request_id, worker, input_hash, claimed_request, action_receipt)
        )
        if self.reconcile_error is not None:
            raise self.reconcile_error
        return self.reconcile


def test_task_store_reconciliation_rpc_uses_exact_claim_binding():
    client = RpcClient()
    store = TaskStore(client)
    req = request()
    action_receipt = receipt()

    assert store.confirm_action_bound(
        REQUEST_ID,
        WORKER_ID,
        request_hash(req),
        req,
        action_receipt,
    ) is True

    assert client.calls == [
        (
            "l_task_confirm_action_bound",
            {
                "p_id": REQUEST_ID,
                "p_worker": WORKER_ID,
                "p_hash": request_hash(req),
                "p_request": req,
                "p_receipt": action_receipt,
            },
        )
    ]


def test_lost_journal_ack_can_be_reconciled_without_replay():
    store = AmbiguousStore(reconcile=True)
    bind(store)
    action_receipt = receipt()
    try:
        assert record_current_action_receipt(action_receipt) is True
        frozen = CONTEXT.action_receipt
    finally:
        CONTEXT.task = None
        CONTEXT.action_receipt = None

    assert len(store.record_calls) == 1
    assert len(store.confirm_calls) == 1
    assert frozen == action_receipt
    assert store.confirm_calls[0] == store.record_calls[0]


def test_reconciliation_miss_remains_fail_closed():
    store = AmbiguousStore(reconcile=False)
    bind(store)
    try:
        with pytest.raises(
            DurableTaskBindingError,
            match="Connected action journal unavailable",
        ):
            record_current_action_receipt(receipt())
    finally:
        CONTEXT.task = None
        CONTEXT.action_receipt = None

    assert len(store.record_calls) == 1
    assert len(store.confirm_calls) == 1


def test_reconciliation_transport_failure_remains_fail_closed_and_private():
    store = AmbiguousStore(
        reconcile_error=ConnectionError("private reconciliation transport detail")
    )
    bind(store)
    try:
        with pytest.raises(DurableTaskBindingError) as exc:
            record_current_action_receipt(receipt())
    finally:
        CONTEXT.task = None
        CONTEXT.action_receipt = None

    assert "private reconciliation transport detail" not in str(exc.value)
    assert len(store.record_calls) == 1
    assert len(store.confirm_calls) == 1


def test_reconciliation_never_retries_the_journal_mutation():
    store = AmbiguousStore(reconcile=True)
    bind(store)
    try:
        assert record_current_action_receipt(receipt()) is True
    finally:
        CONTEXT.task = None
        CONTEXT.action_receipt = None

    assert len(store.record_calls) == 1
    assert len(store.confirm_calls) == 1


def test_layer169_migration_is_read_only_bound_and_service_role_only():
    source = open(
        "supabase/migrations/20260926051707_project_l_layer169_reconcile_action_journal_ack.sql",
        encoding="utf-8",
    ).read()

    assert "create or replace function public.l_task_confirm_action_bound" in source
    assert "language sql" in source
    assert "security invoker" in source
    assert "set search_path=''" in source
    assert "stable" in source
    assert "worker_id = p_worker" in source
    assert "lease_until >= now()" in source
    assert "input_hash = p_hash" in source
    assert "request = p_request" in source
    assert "action_receipt = p_receipt" in source
    assert "from public, anon, authenticated" in source
    assert "to service_role;" in source
    assert "update public.l_chat_tasks" not in source.lower()
    assert "insert into public.l_chat_tasks" not in source.lower()


def test_layer169_release_marker_is_continuous():
    source = open("api/server.py", encoding="utf-8").read()
    layers = [
        int(value)
        for value in re.findall(r'release_layer"?\s*[:=]\s*(\d+)', source)
    ]
    assert len(layers) == 3
    assert len(set(layers)) == 1
    assert layers[0] >= 169
