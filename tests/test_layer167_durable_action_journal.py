"""Layer 167 — provider-confirmed actions are journaled before final answer save."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import threading
from uuid import uuid4

import pytest

from core.cognition.action_receipt import build_action_receipt
from core.cognition.delivery_integrity import seal_chat_delivery_payload
from core.cognition.durable_tasks import (
    CONTEXT,
    DurableTaskBindingError,
    TaskStore,
    record_current_action_receipt,
    request_hash,
)
from services import google_workspace_service as google
from services.capability_router_service import route_capability


REQUEST_ID = "10000000-0000-4000-8000-000000000167"
WORKER_ID = "20000000-0000-4000-8000-000000000167"


def request():
    return {
        "request_id": REQUEST_ID,
        "message": "add to my tasks: call electrician",
    }


def receipt(resource_id="google-task-167"):
    return build_action_receipt(
        request_id=REQUEST_ID,
        capability="google_tasks",
        action="create",
        resource_id=resource_id,
        subject="call electrician",
    )


class RecordingStore:
    def __init__(self, record_ok=True):
        self.record_ok = record_ok
        self.recorded = []

    def record_action_bound(
        self, request_id, worker, input_hash, claimed_request, action_receipt
    ):
        self.recorded.append(
            (request_id, worker, input_hash, claimed_request, action_receipt)
        )
        return self.record_ok


class Executable:
    def __init__(self, value, events=None, event=None):
        self.value = value
        self.events = events
        self.event = event

    def execute(self):
        if self.events is not None and self.event is not None:
            self.events.append(self.event)
        return self.value


class TaskLists:
    def list(self, **_kwargs):
        return Executable({"items": [{"id": "list-167"}]})


class Tasks:
    def __init__(self, events):
        self.events = events

    def insert(self, **kwargs):
        title = kwargs["body"]["title"]
        return Executable(
            {"id": "google-task-167", "title": title},
            self.events,
            ("provider_insert", title),
        )

    def list(self, **_kwargs):
        return Executable({"items": []})


class GoogleService:
    def __init__(self, events):
        self.events = events

    def tasklists(self):
        return TaskLists()

    def tasks(self):
        return Tasks(self.events)


class RpcClient:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=True))


class Query:
    def __init__(self, row):
        self.row = row

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        return SimpleNamespace(data=[dict(self.row)])


class QueryClient:
    def __init__(self, row):
        self.row = row

    def table(self, _name):
        return Query(self.row)


def bind_context(store):
    req = request()
    CONTEXT.task = (
        store,
        REQUEST_ID,
        WORKER_ID,
        request_hash(req),
        req,
        threading.Event(),
    )


def test_task_store_action_journal_rpc_uses_exact_claim_binding():
    client = RpcClient()
    store = TaskStore(client)
    req = request()
    action_receipt = receipt()

    assert store.record_action_bound(
        REQUEST_ID,
        WORKER_ID,
        request_hash(req),
        req,
        action_receipt,
    ) is True

    assert client.calls == [
        (
            "l_task_record_action_bound",
            {
                "p_id": REQUEST_ID,
                "p_worker": WORKER_ID,
                "p_hash": request_hash(req),
                "p_request": req,
                "p_receipt": action_receipt,
            },
        )
    ]


def test_current_action_receipt_is_journaled_immediately():
    store = RecordingStore()
    bind_context(store)
    try:
        assert record_current_action_receipt(receipt()) is True
    finally:
        CONTEXT.task = None

    assert len(store.recorded) == 1
    assert store.recorded[0][0] == REQUEST_ID
    assert store.recorded[0][4]["resource_id"] == "google-task-167"


def test_action_journal_rejection_sets_binding_loss_and_stops():
    store = RecordingStore(record_ok=False)
    bind_context(store)
    lost = CONTEXT.task[5]
    try:
        with pytest.raises(DurableTaskBindingError):
            record_current_action_receipt(receipt())
    finally:
        CONTEXT.task = None

    assert lost.is_set() is True
    assert len(store.recorded) == 1


def test_action_journal_transport_uncertainty_stops_safely():
    class Store(RecordingStore):
        def record_action_bound(self, *args, **kwargs):
            raise ConnectionError("private upstream detail")

    store = Store()
    bind_context(store)
    try:
        with pytest.raises(
            DurableTaskBindingError,
            match="Connected action journal unavailable",
        ) as exc:
            record_current_action_receipt(receipt())
    finally:
        CONTEXT.task = None

    assert "private upstream detail" not in str(exc.value)


def test_non_durable_action_receipt_journal_is_noop():
    CONTEXT.task = None
    assert record_current_action_receipt(
        build_action_receipt(
            request_id="",
            capability="google_tasks",
            action="create",
            resource_id="direct-task",
            subject="direct action",
        )
    ) is False


def test_google_provider_confirmation_is_journaled_before_route_returns(monkeypatch):
    events = []
    store = RecordingStore()
    monkeypatch.setattr(
        google,
        "_google_service",
        lambda *_args: GoogleService(events),
    )
    bind_context(store)
    try:
        route = route_capability(
            "add to my tasks: call electrician",
            write_guard=lambda _stage: None,
        )
    finally:
        CONTEXT.task = None

    assert events == [("provider_insert", "call electrician")]
    assert len(store.recorded) == 1
    assert route["status"] == "ok"
    assert route["action_receipt"] == store.recorded[0][4]


def test_provider_action_then_journal_rejection_cannot_be_clean_success(monkeypatch):
    events = []
    store = RecordingStore(record_ok=False)
    monkeypatch.setattr(
        google,
        "_google_service",
        lambda *_args: GoogleService(events),
    )
    bind_context(store)
    try:
        with pytest.raises(DurableTaskBindingError):
            route_capability(
                "add to my tasks: call electrician",
                write_guard=lambda _stage: None,
            )
    finally:
        CONTEXT.task = None

    assert events == [("provider_insert", "call electrician")]
    assert len(store.recorded) == 1


def test_interrupted_recovery_surfaces_valid_durable_action_journal():
    action_receipt = receipt()
    req = request()
    row = {
        "status": "interrupted",
        "result": None,
        "action_receipt": action_receipt,
        "request": req,
        "input_hash": request_hash(req),
        "checkpoint": "connected_action_recorded",
        "lease_until": None,
        "created_at": "2026-09-26T03:00:00Z",
        "updated_at": "2026-09-26T03:00:01Z",
    }

    result = TaskStore(QueryClient(row)).get(REQUEST_ID, "x" * 64)

    assert result["status"] == "interrupted"
    assert result["action_journal_integrity"]["valid"] is True
    assert result["action_journal_integrity"]["present"] is True
    assert result["result"]["error"] is True
    assert "connected action was confirmed" in result["result"]["reply"].lower()
    assert "before submitting the action again" in result["result"]["reply"].lower()


def test_ready_recovery_rejects_result_that_disagrees_with_journal():
    journal = receipt("journal-task")
    payload_receipt = receipt("different-task")
    req = request()
    payload = seal_chat_delivery_payload(
        {
            "reply": "Task created.",
            "route": {"action_receipt": payload_receipt},
        },
        request_id=REQUEST_ID,
    )
    row = {
        "status": "ready",
        "result": payload,
        "action_receipt": journal,
        "request": req,
        "input_hash": request_hash(req),
        "checkpoint": "ready",
        "lease_until": None,
        "created_at": "2026-09-26T03:00:00Z",
        "updated_at": "2026-09-26T03:00:01Z",
    }

    result = TaskStore(QueryClient(row)).get(REQUEST_ID, "x" * 64)

    assert result["status"] == "failed"
    assert result["action_journal_integrity"]["valid"] is False
    assert "journal verification" in result["result"]["reply"].lower()


def test_ready_recovery_accepts_matching_journal_and_payload():
    journal = receipt()
    req = request()
    payload = seal_chat_delivery_payload(
        {
            "reply": "Task created.",
            "route": {"action_receipt": journal},
        },
        request_id=REQUEST_ID,
    )
    row = {
        "status": "ready",
        "result": payload,
        "action_receipt": journal,
        "request": req,
        "input_hash": request_hash(req),
        "checkpoint": "ready",
        "lease_until": None,
        "created_at": "2026-09-26T03:00:00Z",
        "updated_at": "2026-09-26T03:00:01Z",
    }

    result = TaskStore(QueryClient(row)).get(REQUEST_ID, "x" * 64)

    assert result["status"] == "ready"
    assert result["action_journal_integrity"]["valid"] is True
    assert result["action_journal_integrity"]["payload_bound"] is True


def test_expired_running_task_with_journal_becomes_interrupted_with_warning():
    action_receipt = receipt()
    req = request()
    expired = (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat()
    row = {
        "status": "running",
        "result": None,
        "action_receipt": action_receipt,
        "request": req,
        "input_hash": request_hash(req),
        "checkpoint": "connected_action_recorded",
        "lease_until": expired,
        "created_at": "2026-09-26T03:00:00Z",
        "updated_at": "2026-09-26T03:00:01Z",
    }

    result = TaskStore(QueryClient(row)).get(REQUEST_ID, "x" * 64)

    assert result["status"] == "interrupted"
    assert "connected action was confirmed" in result["result"]["reply"].lower()


def test_layer167_migration_is_bound_and_service_role_only():
    source = open(
        "supabase/migrations/20260926034242_project_l_layer167_durable_action_journal.sql",
        encoding="utf-8",
    ).read()
    assert "add column if not exists action_receipt jsonb" in source
    assert "create or replace function public.l_task_record_action_bound" in source
    assert "security invoker" in source
    assert "set search_path=''" in source
    assert "and input_hash = p_hash" in source
    assert "and request = p_request" in source
    assert "(action_receipt is null or action_receipt = p_receipt)" in source
    assert "p_result #> '{route,action_receipt}' = action_receipt" in source
    assert "from public, anon, authenticated" in source
    assert "to service_role;" in source


def test_layer167_release_marker_is_continuous():
    source = open("api/server.py", encoding="utf-8").read()
    assert source.count('"release_layer": 167') == 2
    assert source.count("release_layer=167") == 1
