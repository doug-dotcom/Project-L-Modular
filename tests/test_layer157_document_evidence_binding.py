"""Layer 157 — bind document answers to the exact source request at write and recovery."""
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest

from core.cognition.document_evidence import (
    require_document_evidence_binding,
    verify_document_evidence_binding,
)
from core.cognition.durable_tasks import TaskRunner, TaskStore


REQUEST_ID = "00000000-0000-4000-8000-000000000157"
TOKEN = "x" * 64
DOCUMENT_ID = "11111111-1111-4111-8111-111111111157"
SHA = "a" * 64


def request():
    return {
        "kind": "document_evidence",
        "request_id": REQUEST_ID,
        "user_id": str(uuid4()),
        "document_id": DOCUMENT_ID,
        "page": 2,
        "question": "What does this page say?",
        "source_sha256": SHA,
    }


def answer(**evidence_changes):
    evidence = {
        "document_id": DOCUMENT_ID,
        "filename": "source.pdf",
        "page": 2,
        "sha256": SHA,
        "kind": "pdf_text",
        "quotes": ["Exact source text"],
    }
    evidence.update(evidence_changes)
    return {"reply": "Bound answer", "evidence": evidence, "memory_written": False}


def test_matching_document_evidence_is_bound():
    check = verify_document_evidence_binding(request(), answer())
    assert check["valid"] is True
    assert check["status"] == "verified"
    assert check["bound"] is True
    assert check["issues"] == []


@pytest.mark.parametrize(
    "payload,issue",
    [
        (answer(document_id="22222222-2222-4222-8222-222222222222"), "document_id_mismatch"),
        (answer(page=1), "physical_page_mismatch"),
        (answer(sha256="b" * 64), "source_sha256_mismatch"),
        (answer(filename=""), "source_filename_missing"),
        ({"reply": "No source"}, "document_evidence_missing"),
    ],
)
def test_document_evidence_mismatch_fails_closed(payload, issue):
    check = verify_document_evidence_binding(request(), payload)
    assert check["valid"] is False
    assert check["status"] == "mismatch"
    assert issue in check["issues"]
    with pytest.raises(ValueError, match="document_evidence_binding_mismatch"):
        require_document_evidence_binding(request(), payload)


def test_non_document_task_is_not_affected():
    check = verify_document_evidence_binding({"kind": "chat"}, {"reply": "Normal chat"})
    assert check == {
        "version": "1.0",
        "status": "not_applicable",
        "valid": True,
        "bound": False,
        "issues": [],
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


def stored_row(payload):
    return {
        "status": "ready",
        "result": payload,
        "request": request(),
        "checkpoint": "done",
        "lease_until": None,
        "created_at": "2026-09-25T00:00:00+00:00",
        "updated_at": "2026-09-25T00:00:01+00:00",
    }


def test_saved_document_answer_rechecks_source_binding_before_return():
    result = TaskStore(Client(stored_row(answer()))).get(REQUEST_ID, TOKEN)
    assert result["status"] == "ready"
    assert result["document_evidence_binding"]["valid"] is True
    assert "request" not in result


def test_saved_document_answer_with_wrong_page_is_withheld():
    result = TaskStore(Client(stored_row(answer(page=1)))).get(REQUEST_ID, TOKEN)
    assert result["status"] == "failed"
    assert result["result"]["error"] is True
    assert "source binding verification" in result["result"]["reply"]
    assert result["document_evidence_binding"]["valid"] is False
    assert "physical_page_mismatch" in result["document_evidence_binding"]["issues"]
    assert "request" not in result


class FakeStore:
    def __init__(self):
        self.finished = []

    def progress(self, *args, **kwargs):
        return True

    def finish(self, request_id, worker, payload, status="ready"):
        self.finished.append((status, payload))
        return True


def test_runner_never_persists_mismatched_document_answer_as_ready():
    store = FakeStore()
    TaskRunner(store, lambda _: answer(page=1)).run_one(
        {"request_id": REQUEST_ID, "request": request()},
        str(uuid4()),
    )
    assert len(store.finished) == 1
    status, payload = store.finished[0]
    assert status == "failed"
    assert payload["error"] is True
    assert payload["reply"] != "Bound answer"
