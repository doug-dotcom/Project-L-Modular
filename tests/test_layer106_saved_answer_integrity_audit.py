"""Layer 106: owner-scoped saved-answer integrity audit."""

from types import SimpleNamespace as NS

import pytest

from core.cognition.answer_authenticity import (
    ACTIVE_KEY_ID_ENV,
    KEY_ENV_PREFIX,
    SIGNING_KEY_ENV,
    VERIFY_KEY_IDS_ENV,
    sign_answer_provenance,
)
from core.cognition.answer_provenance import build_answer_provenance
from core.cognition.delivery_integrity import seal_chat_delivery_payload
from core.cognition.recovery_provenance import (
    PROTOCOL_VERSION,
    mark_answer_provenance_required,
)
from core.cognition.release_provenance import build_release_provenance
from core.cognition.saved_answer_integrity_audit import (
    load_saved_answer_integrity_audit,
    summarise_saved_answer_integrity,
)


REQUEST_ID = "00000000-0000-4000-8000-000000000106"
TOKEN = "x" * 64
COMMIT = "f" * 40
REPLY = "PRIVATE SAVED ANSWER TEXT MUST NEVER LEAK"
LEGACY_KEY = "L" * 64
KEY_ID = "k2-2026-09"
KEY = "2" * 64


def key_env_name(key_id):
    return KEY_ENV_PREFIX + key_id.upper().replace("-", "_")


def runtime_env():
    return {
        "RAILWAY_GIT_REPO_OWNER": "doug-dotcom",
        "RAILWAY_GIT_REPO_NAME": "Project-L-Modular",
        "RAILWAY_GIT_BRANCH": "main",
        "RAILWAY_GIT_COMMIT_SHA": COMMIT,
        "RAILWAY_PROJECT_NAME": "profound-wonder",
        "RAILWAY_SERVICE_NAME": "Project-L-Modular",
        "RAILWAY_ENVIRONMENT_NAME": "production",
        SIGNING_KEY_ENV: LEGACY_KEY,
        ACTIVE_KEY_ID_ENV: KEY_ID,
        VERIFY_KEY_IDS_ENV: KEY_ID,
        key_env_name(KEY_ID): KEY,
    }


def signed_payload(env=None):
    env = env or runtime_env()
    release = build_release_provenance(env)
    model = {"status": "complete", "model_id": "fixture-model"}
    context = {"version": "1.0", "mode": "lean", "rendered_chars": 1000}
    persistence = {"version": "1.0", "status": "verified", "valid": True}
    answer = build_answer_provenance(
        request_id=REQUEST_ID,
        final_reply=REPLY,
        release_provenance=release,
        model_receipt=model,
        context_budget=context,
        assistant_persistence=persistence,
        release_layer=106,
    )
    authenticity = sign_answer_provenance(answer, environ=env)
    payload = {
        "reply": REPLY,
        "server": "vx",
        "cognition": {
            "version": "14.10",
            "runtime": {"status": "complete", "fallback_used": False},
            "release_provenance": release,
            "answer_provenance": answer,
            "answer_authenticity": authenticity,
            "model_receipt": model,
            "context_budget": context,
            "assistant_persistence": persistence,
        },
    }
    payload = mark_answer_provenance_required(
        payload,
        protocol_version=PROTOCOL_VERSION,
    )
    return seal_chat_delivery_payload(payload, request_id=REQUEST_ID)


def test_valid_keyring_answer_is_counted_without_returning_private_text(monkeypatch):
    env = runtime_env()
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    report = summarise_saved_answer_integrity([{
        "request_id": REQUEST_ID,
        "created_at": "2026-09-24T00:00:00+00:00",
        "status": "ready",
        "result": signed_payload(env),
    }])

    assert report["answers_observed"] == 1
    assert report["invalid_answers"] == 0
    assert report["delivery_integrity"]["verified_bound"] == 1
    assert report["recovery_integrity"]["verified_authentic_production"] == 1
    assert report["protocol_versions"]["2.0"] == 1
    assert report["release_commits"][COMMIT] == 1
    assert report["answer_authenticity_keys"][KEY_ID] == 1
    assert report["current_protocol"]["verified_authentic_production"] == 1
    assert report["findings"] == []

    text = str(report)
    assert REPLY not in text
    assert REQUEST_ID not in text
    assert KEY not in text
    assert LEGACY_KEY not in text
    assert report["privacy"]["answer_text_returned"] is False
    assert report["privacy"]["raw_request_ids_returned"] is False


def test_invalid_signature_is_reported_by_issue_code_with_hashed_reference(monkeypatch):
    env = runtime_env()
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    payload = signed_payload(env)
    body = dict(payload)
    body.pop("delivery_receipt")
    cognition = dict(body["cognition"])
    authenticity = dict(cognition["answer_authenticity"])
    authenticity["signature"] = "0" * 64
    cognition["answer_authenticity"] = authenticity
    body["cognition"] = cognition
    resealed = seal_chat_delivery_payload(body, request_id=REQUEST_ID)

    report = summarise_saved_answer_integrity([{
        "request_id": REQUEST_ID,
        "created_at": "2026-09-24T00:00:00+00:00",
        "status": "ready",
        "result": resealed,
    }])

    assert report["invalid_answers"] == 1
    assert report["recovery_integrity"]["invalid"] == 1
    assert report["issue_codes"]["answer_authenticity_verification_failed"] == 1
    assert report["issue_codes"]["answer_authenticity_signature_mismatch"] == 1
    assert len(report["findings"]) == 1
    assert len(report["findings"][0]["request_ref"]) == 12
    assert report["findings"][0]["request_ref"] != REQUEST_ID
    assert REPLY not in str(report)


def test_legacy_answer_is_visible_as_legacy_not_a_false_failure():
    legacy = seal_chat_delivery_payload(
        {"reply": "older answer", "server": "vx"},
        request_id=REQUEST_ID,
    )
    report = summarise_saved_answer_integrity([{
        "request_id": REQUEST_ID,
        "created_at": "2026-09-24T00:00:00+00:00",
        "status": "ready",
        "result": legacy,
    }])

    assert report["invalid_answers"] == 0
    assert report["recovery_integrity"]["legacy_no_answer_provenance"] == 1
    assert report["protocol_versions"]["none"] == 1
    assert report["answer_authenticity_keys"]["unsigned_legacy"] == 1
    assert report["legacy_answers_observed"] == 1


def test_ready_without_result_is_flagged_without_guessing_content():
    report = summarise_saved_answer_integrity([{
        "request_id": REQUEST_ID,
        "created_at": "2026-09-24T00:00:00+00:00",
        "status": "ready",
        "result": None,
    }])

    assert report["delivery_integrity"]["no_result"] == 1
    assert report["issue_codes"]["ready_without_result"] == 1
    assert report["findings"][0]["status"] == "ready_without_result"
    assert report["claims"]["answer_quality"] == "not_scored"


def test_duplicates_and_malformed_rows_are_not_double_counted():
    payload = seal_chat_delivery_payload(
        {"reply": "older answer", "server": "vx"},
        request_id=REQUEST_ID,
    )
    rows = [
        {"request_id": REQUEST_ID, "status": "ready", "result": payload},
        {"request_id": REQUEST_ID, "status": "ready", "result": payload},
        {"request_id": "", "status": "ready", "result": payload},
        "malformed",
    ]
    report = summarise_saved_answer_integrity(rows)

    assert report["answers_observed"] == 1
    assert report["duplicate_rows_ignored"] == 1
    assert report["malformed_rows_ignored"] == 2


def test_key_retirement_is_never_automatically_declared_safe(monkeypatch):
    env = runtime_env()
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    report = summarise_saved_answer_integrity([{
        "request_id": REQUEST_ID,
        "status": "ready",
        "result": signed_payload(env),
    }])

    assert report["key_retirement"]["decision"] == "not_automated"
    assert report["key_retirement"]["observed_key_references"][KEY_ID] == 1
    assert "not proof" in report["key_retirement"]["note"].lower()


class Query:
    def __init__(self, rows, calls):
        self.rows = rows
        self.calls = calls

    def select(self, columns):
        self.calls.append(("select", columns))
        return self

    def eq(self, column, value):
        self.calls.append(("eq", column, value))
        return self

    def order(self, column, desc=False):
        self.calls.append(("order", column, desc))
        return self

    def limit(self, value):
        self.calls.append(("limit", value))
        return self

    def execute(self):
        return NS(data=self.rows)


class Client:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def table(self, name):
        self.calls.append(("table", name))
        return Query(self.rows, self.calls)


def test_loader_is_owner_scoped_bounded_and_read_only():
    client = Client([])
    report = load_saved_answer_integrity_audit(client, TOKEN, 25)

    assert report["status"] == "no_data"
    assert report["sample"] == {
        "scope": "recovery_token_owner",
        "order": "newest_first",
        "limit": 25,
        "read_only": True,
    }
    assert ("table", "l_chat_tasks") in client.calls
    assert any(call[0] == "eq" and call[1] == "user_id" for call in client.calls)
    assert any(call[0] == "eq" and call[1] == "owner_hash" for call in client.calls)
    assert ("order", "created_at", True) in client.calls
    assert ("limit", 25) in client.calls
    assert not any(call[0] in {"insert", "update", "delete", "upsert"} for call in client.calls)


@pytest.mark.parametrize("limit", [0, 101, 1.5, "50"])
def test_loader_rejects_unbounded_or_non_integer_limits(limit):
    with pytest.raises(ValueError, match="Choose between 1 and 100 tasks"):
        load_saved_answer_integrity_audit(Client([]), TOKEN, limit)


def test_server_integrity_audit_endpoint_uses_existing_task_store(monkeypatch):
    from api import server

    client = Client([])
    monkeypatch.setattr(server.task_store, "client", client)

    result = server.cognition_integrity_audit(
        limit=10,
        x_l_recovery_token=TOKEN,
    )
    assert result["mode"] == "saved_answer_integrity_audit"
    assert result["sample"]["scope"] == "recovery_token_owner"
    assert result["privacy"]["answer_text_returned"] is False


def test_server_surfaces_layer106_integrity_audit_readiness():
    from pathlib import Path

    source = Path("api/server.py").read_text(encoding="utf-8")
    assert '"release_layer":' in source
    assert '"saved_answer_integrity_audit_ready": True' in source
    assert '@app.get("/cognition/integrity-audit")' in source
    assert "load_saved_answer_integrity_audit(" in source
