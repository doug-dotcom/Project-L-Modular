"""Layer 165 — connected actions carry request-bound, recoverable receipts."""

from types import SimpleNamespace
import re
from uuid import uuid4

import pytest

from core.cognition.action_receipt import (
    build_action_receipt,
    verify_action_receipt,
    verify_payload_action_receipt,
)
from core.cognition.delivery_integrity import seal_chat_delivery_payload
from core.cognition.durable_tasks import CONTEXT, TaskStore, request_hash
from services import google_workspace_service as google
from services.capability_router_service import route_capability


REQUEST_ID = "10000000-0000-4000-8000-000000000165"
CLAIM_TOKEN = "30000000-0000-4000-8000-000000000165"


class Executable:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class TaskLists:
    def list(self, **_kwargs):
        return Executable({"items": [{"id": "list-165"}]})


class Tasks:
    def __init__(self, include_id=True):
        self.include_id = include_id

    def insert(self, **kwargs):
        body = kwargs["body"]
        value = {"title": body["title"]}
        if self.include_id:
            value["id"] = "google-task-165"
        return Executable(value)

    def list(self, **_kwargs):
        return Executable({"items": []})


class GoogleService:
    def __init__(self, include_id=True):
        self.include_id = include_id

    def tasklists(self):
        return TaskLists()

    def tasks(self):
        return Tasks(include_id=self.include_id)


class ResultQuery:
    def __init__(self, row):
        self.row = row

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        return SimpleNamespace(data=[self.row])


class ResultClient:
    def __init__(self, row):
        self.row = row

    def table(self, _name):
        return ResultQuery(self.row)


class RecordingStore(TaskStore):
    def __init__(self):
        super().__init__(None)
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return True


def task_context(request_id=REQUEST_ID):
    request = {"request_id": request_id, "message": "add to my tasks: call electrician"}
    store = RecordingStore()
    worker = str(uuid4())
    store._remember_claim_token(worker, CLAIM_TOKEN)
    return (store, request_id, worker, request_hash(request), request)


def test_google_tasks_emits_request_bound_confirmed_receipt(monkeypatch):
    monkeypatch.setattr(
        google,
        "_google_service",
        lambda *_args: GoogleService(include_id=True),
    )
    CONTEXT.task = task_context()
    try:
        route = route_capability(
            "add to my tasks: call electrician",
            write_guard=lambda _stage: None,
        )
    finally:
        CONTEXT.task = None

    receipt = route["action_receipt"]
    verification = route["action_receipt_verification"]
    assert route["status"] == "ok"
    assert receipt["status"] == "confirmed"
    assert receipt["request_id"] == REQUEST_ID
    assert receipt["request_bound"] is True
    assert receipt["capability"] == "google_tasks"
    assert receipt["action"] == "create"
    assert receipt["resource_id"] == "google-task-165"
    assert len(receipt["subject_sha256"]) == 64
    assert "call electrician" not in str(receipt)
    assert verification["valid"] is True
    assert verification["request_bound"] is True


def test_missing_provider_resource_id_is_not_clean_success(monkeypatch):
    monkeypatch.setattr(
        google,
        "_google_service",
        lambda *_args: GoogleService(include_id=False),
    )
    CONTEXT.task = task_context()
    try:
        route = route_capability(
            "add to my tasks: call electrician",
            write_guard=lambda _stage: None,
        )
    finally:
        CONTEXT.task = None

    assert route["status"] == "error"
    assert route["action_receipt_verification"]["valid"] is False
    assert "action_receipt_resource_id_invalid" in route["action_receipt_verification"]["issues"]
    assert "check google tasks before retrying" in route["reply"].lower()


def test_receipt_hash_and_request_binding_are_semantically_verified():
    receipt = build_action_receipt(
        request_id=REQUEST_ID,
        capability="google_tasks",
        action="create",
        resource_id="task-1",
        subject="call electrician",
    )
    assert verify_action_receipt(receipt, expected_request_id=REQUEST_ID)["valid"] is True

    wrong_request = verify_action_receipt(
        receipt,
        expected_request_id="20000000-0000-4000-8000-000000000165",
    )
    assert wrong_request["valid"] is False
    assert "action_receipt_request_id_mismatch" in wrong_request["issues"]

    tampered = dict(receipt)
    tampered["resource_id"] = "different-task"
    changed = verify_action_receipt(tampered, expected_request_id=REQUEST_ID)
    assert changed["valid"] is False
    assert "action_receipt_hash_mismatch" in changed["issues"]


def test_durable_write_rejects_wrong_request_receipt_before_rpc():
    receipt = build_action_receipt(
        request_id="20000000-0000-4000-8000-000000000165",
        capability="google_tasks",
        action="create",
        resource_id="task-2",
        subject="call electrician",
    )
    payload = seal_chat_delivery_payload(
        {
            "reply": "Task created.",
            "route": {"action_receipt": receipt},
        },
        request_id=REQUEST_ID,
    )
    request = {"request_id": REQUEST_ID, "message": "fixture"}
    store = RecordingStore()

    with pytest.raises(ValueError, match="connected_action_receipt_mismatch"):
        store.finish_bound(
            REQUEST_ID,
            "worker",
            request_hash(request),
            request,
            payload,
        )

    assert store.calls == []


def test_durable_recovery_withholds_semantically_invalid_receipt():
    receipt = build_action_receipt(
        request_id="20000000-0000-4000-8000-000000000165",
        capability="google_tasks",
        action="create",
        resource_id="task-3",
        subject="call electrician",
    )
    payload = seal_chat_delivery_payload(
        {
            "reply": "Task created.",
            "route": {"action_receipt": receipt},
        },
        request_id=REQUEST_ID,
    )
    request = {"request_id": REQUEST_ID, "message": "fixture"}
    row = {
        "status": "ready",
        "result": payload,
        "request": request,
        "input_hash": request_hash(request),
        "checkpoint": "ready",
        "lease_until": None,
        "created_at": "2026-09-26T00:00:00Z",
        "updated_at": "2026-09-26T00:00:01Z",
    }

    result = TaskStore(ResultClient(row)).get(REQUEST_ID, "x" * 64)

    assert result["status"] == "failed"
    assert result["result"]["error"] is True
    assert result["action_receipt_integrity"]["valid"] is False
    assert "connected-action receipt verification" in result["result"]["reply"]


def test_payload_without_connected_action_remains_valid():
    payload = {"reply": "Read-only result", "route": {"capability": "gmail"}}
    check = verify_payload_action_receipt(
        payload,
        expected_request_id=REQUEST_ID,
    )
    assert check == {
        "version": "layer165-connected-action-receipt-1",
        "valid": True,
        "status": "not_present",
        "present": False,
        "request_bound": False,
        "issues": [],
    }


def test_direct_saved_results_also_require_action_receipt_integrity():
    source = open("api/server.py", encoding="utf-8").read()
    validation = source.index("require_payload_action_receipt(")
    storage = source.index("_chat_results[request_id] = {")
    assert validation < storage


def test_layer165_release_marker_is_continuous():
    source = open("api/server.py", encoding="utf-8").read()
    layers = [
        int(value)
        for value in re.findall(r'release_layer"?\s*[:=]\s*(\d+)', source)
    ]
    assert len(layers) == 3
    assert len(set(layers)) == 1
    assert layers[0] >= 165
