"""Layer 108: cold saved-answer recovery certification."""

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
from core.cognition.cold_recovery_certification import (
    VERSION,
    certify_saved_answer_row,
    load_cold_recovery_certification,
)
from core.cognition.delivery_integrity import seal_chat_delivery_payload
from core.cognition.recovery_provenance import (
    PROTOCOL_VERSION,
    mark_answer_provenance_required,
)
from core.cognition.release_provenance import build_release_provenance


REQUEST_ID = "00000000-0000-4000-8000-000000000108"
TOKEN = "x" * 64
CURRENT_COMMIT = "8" * 40
HISTORICAL_COMMIT = "6" * 40
REPLY = "PRIVATE LAYER 108 ANSWER MUST NOT LEAK"
KEY_ID = "k2-2026-09"
KEY = "K" * 64
LEGACY_KEY = "L" * 64


def key_env_name(key_id):
    return KEY_ENV_PREFIX + key_id.upper().replace("-", "_")


def runtime_env(commit=CURRENT_COMMIT):
    return {
        "RAILWAY_GIT_REPO_OWNER": "doug-dotcom",
        "RAILWAY_GIT_REPO_NAME": "Project-L-Modular",
        "RAILWAY_GIT_BRANCH": "main",
        "RAILWAY_GIT_COMMIT_SHA": commit,
        "RAILWAY_PROJECT_NAME": "profound-wonder",
        "RAILWAY_SERVICE_NAME": "Project-L-Modular",
        "RAILWAY_ENVIRONMENT_NAME": "production",
        SIGNING_KEY_ENV: LEGACY_KEY,
        ACTIVE_KEY_ID_ENV: KEY_ID,
        VERIFY_KEY_IDS_ENV: KEY_ID,
        key_env_name(KEY_ID): KEY,
    }


def install_env(monkeypatch, env):
    for name in list(runtime_env()):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)


def signed_payload(*, stored_commit=CURRENT_COMMIT, keyring_env=None):
    keyring_env = keyring_env or runtime_env(CURRENT_COMMIT)
    stored_env = runtime_env(stored_commit)
    release = build_release_provenance(stored_env)
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
        release_layer=108,
    )
    authenticity = sign_answer_provenance(answer, environ=keyring_env)
    body = {
        "reply": REPLY,
        "server": "vx",
        "cognition": {
            "release_provenance": release,
            "answer_provenance": answer,
            "answer_authenticity": authenticity,
            "model_receipt": model,
            "context_budget": context,
            "assistant_persistence": persistence,
        },
    }
    body = mark_answer_provenance_required(
        body,
        protocol_version=PROTOCOL_VERSION,
    )
    return seal_chat_delivery_payload(body, request_id=REQUEST_ID)


def current_release(commit=CURRENT_COMMIT):
    return build_release_provenance(runtime_env(commit))


def ready_row(payload):
    return {
        "request_id": REQUEST_ID,
        "created_at": "2026-09-24T00:00:00+00:00",
        "updated_at": "2026-09-24T00:00:01+00:00",
        "status": "ready",
        "result": payload,
    }


def test_current_release_answer_certifies_from_durable_payload(monkeypatch):
    env = runtime_env()
    install_env(monkeypatch, env)

    report = certify_saved_answer_row(
        ready_row(signed_payload(keyring_env=env)),
        request_id=REQUEST_ID,
        current_release=current_release(),
    )

    assert report["version"] == VERSION
    assert report["status"] == "certified_current_release"
    assert report["certified"] is True
    assert report["release_relationship"] == "current_release"
    assert report["stored_release_commit_sha"] == CURRENT_COMMIT
    assert report["delivery"] == {"valid": True, "bound": True}
    assert report["provenance"]["valid"] is True
    assert report["provenance"]["verified_production"] is True
    assert report["authenticity"]["required"] is True
    assert report["authenticity"]["valid"] is True
    assert report["authenticity"]["authentic"] is True
    assert report["authenticity"]["verification_mode"] == "keyring"
    assert report["authenticity"]["key_id"] == KEY_ID
    assert report["claims"]["recoverability"] == "certified"
    assert report["task_replayed"] is False
    assert report["model_called"] is False
    assert report["memory_written"] is False


def test_historical_release_still_certifies_after_deploy(monkeypatch):
    env = runtime_env(CURRENT_COMMIT)
    install_env(monkeypatch, env)

    report = certify_saved_answer_row(
        ready_row(
            signed_payload(
                stored_commit=HISTORICAL_COMMIT,
                keyring_env=env,
            )
        ),
        request_id=REQUEST_ID,
        current_release=current_release(CURRENT_COMMIT),
    )

    assert report["status"] == "certified_historical_release"
    assert report["certified"] is True
    assert report["release_relationship"] == "historical_release"
    assert report["stored_release_commit_sha"] == HISTORICAL_COMMIT
    assert report["current_release"]["commit_sha"] == CURRENT_COMMIT
    assert report["authenticity"]["authentic"] is True


def test_genuine_legacy_answer_is_readable_but_not_modernly_authenticated(monkeypatch):
    env = runtime_env()
    install_env(monkeypatch, env)
    legacy = seal_chat_delivery_payload(
        {"reply": "old answer", "server": "vx"},
        request_id=REQUEST_ID,
    )

    report = certify_saved_answer_row(
        ready_row(legacy),
        request_id=REQUEST_ID,
        current_release=current_release(),
    )

    assert report["status"] == "legacy_readable_not_modernly_authenticated"
    assert report["certified"] is True
    assert report["release_relationship"] == "legacy_no_release_provenance"
    assert report["provenance"]["present"] is False
    assert report["authenticity"]["required"] is False
    assert report["claims"]["recoverability"] == "certified_legacy_readability"


def test_tampered_signature_fails_cold_certification_without_leaking_answer(monkeypatch):
    env = runtime_env()
    install_env(monkeypatch, env)
    payload = signed_payload(keyring_env=env)

    body = dict(payload)
    body.pop("delivery_receipt")
    cognition = dict(body["cognition"])
    authenticity = dict(cognition["answer_authenticity"])
    authenticity["signature"] = "0" * 64
    cognition["answer_authenticity"] = authenticity
    body["cognition"] = cognition
    tampered = seal_chat_delivery_payload(body, request_id=REQUEST_ID)

    report = certify_saved_answer_row(
        ready_row(tampered),
        request_id=REQUEST_ID,
        current_release=current_release(),
    )

    assert report["status"] == "failed_integrity"
    assert report["certified"] is False
    assert report["claims"]["recoverability"] == "failed"
    assert "answer_authenticity_verification_failed" in report["issues"]
    assert "answer_authenticity_signature_mismatch" in report["issues"]
    text = str(report)
    assert REPLY not in text
    assert REQUEST_ID not in text
    assert KEY not in text
    assert LEGACY_KEY not in text


def test_pending_or_ready_without_result_is_not_falsely_certified():
    pending = certify_saved_answer_row(
        {"status": "running", "result": None},
        request_id=REQUEST_ID,
        current_release=current_release(),
    )
    missing = certify_saved_answer_row(
        {"status": "ready", "result": None},
        request_id=REQUEST_ID,
        current_release=current_release(),
    )

    assert pending["status"] == "not_ready"
    assert pending["certified"] is False
    assert pending["issues"] == ["saved_answer_not_ready"]
    assert missing["issues"] == ["ready_without_result"]


def test_not_found_uses_only_hashed_request_reference():
    report = certify_saved_answer_row(
        None,
        request_id=REQUEST_ID,
        current_release=current_release(),
    )

    assert report["status"] == "not_found"
    assert report["certified"] is False
    assert len(report["request_ref"]) == 12
    assert report["request_ref"] != REQUEST_ID
    assert REQUEST_ID not in str(report)


def test_invalid_request_id_is_rejected():
    with pytest.raises(ValueError, match="valid request ID"):
        certify_saved_answer_row(
            None,
            request_id="not-a-uuid",
            current_release=current_release(),
        )


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


def test_loader_is_exact_owner_scoped_cold_and_read_only(monkeypatch):
    env = runtime_env()
    install_env(monkeypatch, env)
    client = Client([ready_row(signed_payload(keyring_env=env))])

    report = load_cold_recovery_certification(
        client,
        TOKEN,
        REQUEST_ID,
    )

    assert report["certified"] is True
    assert report["sample"] == {
        "scope": "recovery_token_owner_exact_request",
        "database": "l_chat_tasks",
        "read_only": True,
        "limit": 1,
        "in_process_cache_used": False,
    }
    assert ("table", "l_chat_tasks") in client.calls
    assert ("eq", "request_id", REQUEST_ID) in client.calls
    assert any(call[0] == "eq" and call[1] == "user_id" for call in client.calls)
    assert any(call[0] == "eq" and call[1] == "owner_hash" for call in client.calls)
    assert ("limit", 1) in client.calls
    assert not any(
        call[0] in {"insert", "update", "delete", "upsert", "rpc"}
        for call in client.calls
    )


def test_loader_requires_valid_owner_token_and_request_id():
    with pytest.raises(ValueError):
        load_cold_recovery_certification(
            Client([]),
            "short",
            REQUEST_ID,
        )
    with pytest.raises(ValueError):
        load_cold_recovery_certification(
            Client([]),
            TOKEN,
            "bad-id",
        )


def test_server_endpoint_returns_privacy_safe_certificate(monkeypatch):
    from api import server

    env = runtime_env()
    install_env(monkeypatch, env)
    client = Client([ready_row(signed_payload(keyring_env=env))])
    monkeypatch.setattr(server.task_store, "client", client)

    report = server.cognition_recovery_certification(
        request_id=REQUEST_ID,
        x_l_recovery_token=TOKEN,
    )

    assert report["mode"] == "cold_saved_answer_recovery_certification"
    assert report["certified"] is True
    assert report["privacy"]["answer_text_returned"] is False
    assert report["privacy"]["raw_request_id_returned"] is False
    assert REPLY not in str(report)
    assert REQUEST_ID not in str(report)


def test_server_surfaces_layer108_cold_recovery_readiness():
    from pathlib import Path

    source = Path("api/server.py").read_text(encoding="utf-8")
    assert '"release_layer":' in source
    assert '"cold_recovery_certification_ready": True' in source
    assert '@app.get("/cognition/recovery-certification/{request_id}")' in source
    assert "load_cold_recovery_certification(" in source
