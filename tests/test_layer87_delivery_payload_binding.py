import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from core.cognition.delivery_integrity import (
    seal_chat_delivery_payload,
    verify_chat_delivery_payload,
)
from core.cognition.durable_tasks import TaskStore


def base_payload(reply="Exact delivered answer"):
    return {
        "reply": reply,
        "server": "vx",
        "short_term": {
            "assistant_saved": True,
            "assistant_integrity": "verified",
        },
        "cognition": {
            "evidence_evaluation": {
                "status": "citation_checks_passed",
                "final_publication": {
                    "status": "sealed",
                    "valid": True,
                    "receipt_sha256": "a" * 64,
                },
            },
            "assistant_persistence": {
                "status": "verified",
                "valid": True,
                "receipt_sha256": "b" * 64,
            },
        },
    }


def test_layer87_seals_exact_reply_payload_and_request_identity():
    request_id = str(uuid4())
    payload = seal_chat_delivery_payload(
        base_payload(),
        request_id=request_id,
    )

    receipt = payload["delivery_receipt"]
    check = verify_chat_delivery_payload(
        payload,
        expected_request_id=request_id,
    )

    assert check["valid"] is True
    assert check["bound"] is True
    assert check["status"] == "verified"
    assert receipt["status"] == "sealed"
    assert receipt["request_id"] == request_id
    assert len(receipt["reply_sha256"]) == 64
    assert len(receipt["payload_sha256"]) == 64
    assert len(receipt["receipt_sha256"]) == 64
    assert receipt["final_publication_receipt_sha256"] == "a" * 64
    assert receipt["assistant_persistence_receipt_sha256"] == "b" * 64


def test_layer87_delivery_receipt_contains_hashes_not_reply_text():
    private_reply = "PRIVATE DELIVERED RESPONSE"
    payload = seal_chat_delivery_payload(
        base_payload(private_reply),
        request_id=str(uuid4()),
    )

    encoded = json.dumps(payload["delivery_receipt"])

    assert private_reply not in encoded
    assert "reply_sha256" in encoded


def test_layer87_reply_mutation_after_seal_fails_closed():
    request_id = str(uuid4())
    payload = seal_chat_delivery_payload(
        base_payload(),
        request_id=request_id,
    )
    payload["reply"] += " mutated"

    check = verify_chat_delivery_payload(
        payload,
        expected_request_id=request_id,
    )

    assert check["valid"] is False
    assert "delivery_reply_hash_mismatch" in check["issues"]
    assert "delivery_payload_hash_mismatch" in check["issues"]


def test_layer87_nested_payload_mutation_after_seal_is_detected():
    request_id = str(uuid4())
    payload = seal_chat_delivery_payload(
        base_payload(),
        request_id=request_id,
    )
    payload["cognition"]["assistant_persistence"]["status"] = "mismatch"

    check = verify_chat_delivery_payload(
        payload,
        expected_request_id=request_id,
    )

    assert check["valid"] is False
    assert "delivery_payload_hash_mismatch" in check["issues"]


def test_layer87_payload_cannot_be_replayed_under_another_request_id():
    first_request = str(uuid4())
    second_request = str(uuid4())
    payload = seal_chat_delivery_payload(
        base_payload(),
        request_id=first_request,
    )

    check = verify_chat_delivery_payload(
        payload,
        expected_request_id=second_request,
    )

    assert check["valid"] is False
    assert "delivery_request_id_mismatch" in check["issues"]


def test_layer87_tampered_delivery_receipt_is_detected():
    request_id = str(uuid4())
    payload = seal_chat_delivery_payload(
        base_payload(),
        request_id=request_id,
    )
    payload["delivery_receipt"]["reply_sha256"] = "9" * 64

    check = verify_chat_delivery_payload(
        payload,
        expected_request_id=request_id,
    )

    assert check["valid"] is False
    assert "delivery_receipt_hash_mismatch" in check["issues"]
    assert "delivery_reply_hash_mismatch" in check["issues"]


class RecordingStore(TaskStore):
    def __init__(self):
        super().__init__(None)
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return True


def test_layer87_durable_finish_rejects_mutated_bound_payload_before_rpc():
    request_id = str(uuid4())
    payload = seal_chat_delivery_payload(
        base_payload(),
        request_id=request_id,
    )
    payload["reply"] += " changed after seal"
    store = RecordingStore()

    with pytest.raises(ValueError, match="chat_delivery_integrity_mismatch"):
        store.finish(request_id, "worker", payload)

    assert store.calls == []


class ResultQuery:
    def __init__(self, row):
        self.row = row

    def select(self, _columns):
        return self

    def eq(self, _key, _value):
        return self

    def limit(self, _value):
        return self

    def execute(self):
        return SimpleNamespace(data=[self.row])


class ResultClient:
    def __init__(self, row):
        self.row = row

    def table(self, _name):
        return ResultQuery(self.row)


def test_layer87_durable_get_verifies_saved_bound_result():
    request_id = str(uuid4())
    payload = seal_chat_delivery_payload(
        base_payload(),
        request_id=request_id,
    )
    row = {
        "status": "ready",
        "result": payload,
        "checkpoint": "saving_answer",
        "lease_until": None,
        "created_at": "2026-09-21T00:00:00Z",
        "updated_at": "2026-09-21T00:00:01Z",
    }
    store = TaskStore(ResultClient(row))

    result = store.get(request_id, "x" * 64)

    assert result["status"] == "ready"
    assert result["result"]["reply"] == payload["reply"]
    assert result["delivery_integrity"]["valid"] is True
    assert result["delivery_integrity"]["bound"] is True


def test_layer87_durable_get_hides_mutated_saved_result():
    request_id = str(uuid4())
    payload = seal_chat_delivery_payload(
        base_payload("Original answer"),
        request_id=request_id,
    )
    payload["reply"] = "Database-mutated answer"
    row = {
        "status": "ready",
        "result": payload,
        "checkpoint": "saving_answer",
        "lease_until": None,
        "created_at": "2026-09-21T00:00:00Z",
        "updated_at": "2026-09-21T00:00:01Z",
    }
    store = TaskStore(ResultClient(row))

    result = store.get(request_id, "x" * 64)

    assert result["status"] == "failed"
    assert result["result"]["error"] is True
    assert "Original answer" not in json.dumps(result)
    assert "Database-mutated answer" not in json.dumps(result)
    assert result["delivery_integrity"]["valid"] is False


def test_layer87_legacy_unbound_results_remain_readable_during_rollout():
    check = verify_chat_delivery_payload(
        {"reply": "Older saved answer", "server": "vx"},
        expected_request_id=str(uuid4()),
    )

    assert check["valid"] is True
    assert check["bound"] is False
    assert check["status"] == "legacy_unbound"


def test_layer87_live_server_seals_before_cache_and_return():
    source = (Path(__file__).resolve().parents[1] / "api" / "server.py").read_text(
        encoding="utf-8"
    )

    seal_idx = source.rindex("payload = seal_chat_delivery_payload(")
    verify_idx = source.rindex("delivery_check = verify_chat_delivery_payload(")
    store_idx = source.rindex('store_chat_result(request_id, "ready", payload)')
    return_idx = source.rindex("return payload")

    assert seal_idx < verify_idx < store_idx < return_idx
    assert "require_chat_delivery_payload(" in source
    assert "delivery_request_id_mismatch" not in source


def test_layer87_browser_verifies_reply_hash_before_rendering_recovery():
    source = (
        Path(__file__).resolve().parents[1] / "ui" / "index.html"
    ).read_text(encoding="utf-8")

    assert "async function sha256HexText(value)" in source
    assert "async function verifyDeliveryReply(result, requestId)" in source
    assert 'window.crypto.subtle.digest("SHA-256", bytes)' in source
    assert source.count("await verifyDeliveryReply(") >= 2
    assert "recovered answer failed delivery integrity" in source
    assert "saved answer failed delivery integrity verification" in source


def test_layer87_durable_task_store_checks_delivery_on_write_and_read():
    source = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "cognition"
        / "durable_tasks.py"
    ).read_text(encoding="utf-8")

    assert "require_chat_delivery_payload(" in source
    assert "verify_chat_delivery_payload(" in source
    assert "The saved answer failed delivery integrity verification." in source


def test_layer87_evaluation_manifest_exposes_delivery_binding():
    source = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "cognition"
        / "evidence_evaluation.py"
    ).read_text(encoding="utf-8")

    assert '"chat_delivery_payload_binding"' in source


def test_layer87_layer86_guard_accepts_future_continuous_layers():
    source = (
        Path(__file__).resolve().parents[1]
        / "tests"
        / "test_layer86_integrity_regression_ci.py"
    ).read_text(encoding="utf-8")

    assert "max(numbers) + 1" in source
    assert "numbers[-1] == 86" not in source
    assert "len(numbers) == 19" not in source
