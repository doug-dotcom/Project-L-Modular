"""Layer 158 — verify durable request identity and input hash before recovery."""
from types import SimpleNamespace as NS

import pytest

from core.cognition.durable_tasks import (
    TaskStore,
    request_hash,
    verify_task_request_integrity,
)

REQUEST_ID = "00000000-0000-4000-8000-000000000158"
TOKEN = "x" * 64


def req(**changes):
    value = {"request_id": REQUEST_ID, "message": "Synthetic durable request"}
    value.update(changes)
    return value


def payload():
    return {"reply": "Recovered answer"}


@pytest.mark.parametrize(
    "request,input_hash,issue",
    [
        (None, "a" * 64, "request_payload_missing_or_malformed"),
        (req(request_id="00000000-0000-4000-8000-000000000999"), None, "request_id_binding_mismatch"),
        (req(), "bad", "input_hash_shape_invalid"),
        (req(), "b" * 64, "request_hash_mismatch"),
    ],
)
def test_request_integrity_rejects_invalid_stored_request(request, input_hash, issue):
    check = verify_task_request_integrity(REQUEST_ID, request, input_hash)
    assert check["valid"] is False
    assert check["status"] == "mismatch"
    assert issue in check["issues"]


def test_request_integrity_accepts_exact_stored_request():
    request = req()
    check = verify_task_request_integrity(REQUEST_ID, request, request_hash(request))
    assert check == {
        "version": "1.0",
        "status": "verified",
        "valid": True,
        "issues": [],
        "request_id_bound": True,
    }


class Query:
    def __init__(self, row):
        self.row = row

    def select(self, *args):
        return self

    def eq(self, *args):
        return self

    def limit(self, *args):
        return self

    def execute(self):
        return NS(data=[dict(self.row)])


class Client:
    def __init__(self, row):
        self.row = row

    def table(self, name):
        assert name == "l_chat_tasks"
        return Query(self.row)


def row(request, input_hash):
    return {
        "status": "ready",
        "result": payload(),
        "request": request,
        "input_hash": input_hash,
        "checkpoint": "ready",
        "lease_until": None,
        "created_at": "2026-09-25T00:00:00+00:00",
        "updated_at": "2026-09-25T00:00:01+00:00",
    }


def test_recovery_exposes_verified_request_integrity_without_returning_request():
    request = req()
    result = TaskStore(Client(row(request, request_hash(request)))).get(REQUEST_ID, TOKEN)
    assert result["status"] == "ready"
    assert result["request_integrity"]["status"] == "verified"
    assert result["request_integrity"]["valid"] is True
    assert "request" not in result
    assert "input_hash" not in result


@pytest.mark.parametrize(
    "request,input_hash,issue",
    [
        (None, "a" * 64, "request_payload_missing_or_malformed"),
        (req(request_id="00000000-0000-4000-8000-000000000999"), None, "request_id_binding_mismatch"),
        (req(), "bad", "input_hash_shape_invalid"),
        (req(), "b" * 64, "request_hash_mismatch"),
    ],
)
def test_recovery_withholds_answer_when_stored_request_integrity_fails(request, input_hash, issue):
    result = TaskStore(Client(row(request, input_hash))).get(REQUEST_ID, TOKEN)
    assert result["status"] == "failed"
    assert result["result"]["error"] is True
    assert "request integrity verification" in result["result"]["reply"]
    assert result["request_integrity"]["valid"] is False
    assert issue in result["request_integrity"]["issues"]
    assert "request" not in result
    assert "input_hash" not in result


def test_pre_contract_reader_without_selected_request_columns_is_explicitly_unchecked():
    legacy = {
        "status": "ready",
        "result": payload(),
        "checkpoint": "ready",
        "lease_until": None,
        "created_at": "2026-09-25T00:00:00+00:00",
        "updated_at": "2026-09-25T00:00:01+00:00",
    }
    result = TaskStore(Client(legacy)).get(REQUEST_ID, TOKEN)
    assert result["status"] == "ready"
    assert result["request_integrity"]["status"] == "legacy_unchecked"
    assert result["request_integrity"]["valid"] is True
    assert result["request_integrity"]["request_id_bound"] is False
