"""Layer 103: provenance verification on saved-answer recovery."""

from types import SimpleNamespace as NS

import pytest

from core.cognition.answer_provenance import build_answer_provenance
from core.cognition.delivery_integrity import seal_chat_delivery_payload
from core.cognition.durable_tasks import TaskStore, request_hash
from core.cognition.recovery_provenance import (
    LEGACY_PROTOCOL_VERSION,
    PROTOCOL_KEY,
    PROTOCOL_VERSION,
    mark_answer_provenance_required,
    require_recovered_answer_payload,
    verify_recovered_answer_payload,
)
from core.cognition.release_provenance import build_release_provenance


REQUEST_ID = "00000000-0000-4000-8000-000000000103"
TOKEN = "x" * 64
COMMIT = "c" * 40
REPLY = "Layer 103 synthetic saved answer."


def production_env():
    return {
        "RAILWAY_GIT_REPO_OWNER": "doug-dotcom",
        "RAILWAY_GIT_REPO_NAME": "Project-L-Modular",
        "RAILWAY_GIT_BRANCH": "main",
        "RAILWAY_GIT_COMMIT_SHA": COMMIT,
        "RAILWAY_PROJECT_NAME": "profound-wonder",
        "RAILWAY_SERVICE_NAME": "Project-L-Modular",
        "RAILWAY_ENVIRONMENT_NAME": "production",
        "L_ANSWER_PROVENANCE_SIGNING_KEY": "k" * 64,
    }


def components():
    release = build_release_provenance(production_env())
    model = {"status": "complete", "model_id": "fixture-model"}
    context = {"version": "1.0", "mode": "lean", "rendered_chars": 900}
    persistence = {"version": "1.0", "status": "verified", "valid": True}
    return release, model, context, persistence


def answer_payload(*, marked=True, release_layer=103):
    release, model, context, persistence = components()
    answer = build_answer_provenance(
        request_id=REQUEST_ID,
        final_reply=REPLY,
        release_provenance=release,
        model_receipt=model,
        context_budget=context,
        assistant_persistence=persistence,
        release_layer=release_layer,
    )
    body = {
        "reply": REPLY,
        "server": "vx",
        "cognition": {
            "release_provenance": release,
            "answer_provenance": answer,
            "model_receipt": model,
            "context_budget": context,
            "assistant_persistence": persistence,
        },
    }
    if marked:
        body = mark_answer_provenance_required(
            body,
            protocol_version=LEGACY_PROTOCOL_VERSION,
        )
    return seal_chat_delivery_payload(body, request_id=REQUEST_ID)


def test_layer103_marked_answer_requires_and_verifies_provenance():
    payload = answer_payload()
    check = verify_recovered_answer_payload(
        payload,
        expected_request_id=REQUEST_ID,
    )

    assert payload[PROTOCOL_KEY] == LEGACY_PROTOCOL_VERSION
    assert check["valid"] is True
    assert check["status"] == "verified_production"
    assert check["provenance_required"] is True
    assert check["provenance_present"] is True
    assert check["delivery_integrity"]["valid"] is True
    assert check["answer_provenance"]["verified_production"] is True


def test_protocol_marker_prevents_missing_provenance_downgrade():
    payload = answer_payload()
    body = dict(payload)
    body.pop("delivery_receipt")
    cognition = dict(body["cognition"])
    cognition.pop("answer_provenance")
    body["cognition"] = cognition
    resealed = seal_chat_delivery_payload(body, request_id=REQUEST_ID)

    check = verify_recovered_answer_payload(
        resealed,
        expected_request_id=REQUEST_ID,
    )
    assert check["valid"] is False
    assert "answer_provenance_required_but_missing" in check["issues"]


def test_bound_component_change_fails_even_after_delivery_is_resealed():
    payload = answer_payload()
    body = dict(payload)
    body.pop("delivery_receipt")
    cognition = dict(body["cognition"])
    cognition["model_receipt"] = {
        **cognition["model_receipt"],
        "model_id": "changed-model",
    }
    body["cognition"] = cognition
    resealed = seal_chat_delivery_payload(body, request_id=REQUEST_ID)

    check = verify_recovered_answer_payload(
        resealed,
        expected_request_id=REQUEST_ID,
    )
    assert check["valid"] is False
    assert "answer_provenance_verification_failed" in check["issues"]
    assert "response_model_receipt_mismatch" in check["answer_provenance"]["issues"]


def test_unsupported_protocol_fails_closed():
    payload = answer_payload()
    body = dict(payload)
    body.pop("delivery_receipt")
    body[PROTOCOL_KEY] = "999.0"
    resealed = seal_chat_delivery_payload(body, request_id=REQUEST_ID)

    check = verify_recovered_answer_payload(
        resealed,
        expected_request_id=REQUEST_ID,
    )
    assert check["valid"] is False
    assert "answer_provenance_protocol_unsupported" in check["issues"]


def test_layer102_receipt_without_protocol_remains_verified_compatibility():
    payload = answer_payload(marked=False, release_layer=102)
    check = verify_recovered_answer_payload(
        payload,
        expected_request_id=REQUEST_ID,
    )

    assert check["valid"] is True
    assert check["status"] == "verified_layer102_compat"
    assert check["provenance_required"] is False
    assert check["provenance_present"] is True


def test_genuine_pre_provenance_legacy_answer_remains_readable():
    payload = seal_chat_delivery_payload(
        {"reply": "Older saved answer", "server": "vx"},
        request_id=REQUEST_ID,
    )
    check = verify_recovered_answer_payload(
        payload,
        expected_request_id=REQUEST_ID,
    )

    assert check["valid"] is True
    assert check["status"] == "legacy_no_answer_provenance"
    assert check["provenance_required"] is False
    assert check["provenance_present"] is False


def test_malformed_present_provenance_does_not_downgrade_to_legacy():
    body = {
        "reply": REPLY,
        "server": "vx",
        "cognition": {"answer_provenance": "malformed"},
    }
    payload = seal_chat_delivery_payload(body, request_id=REQUEST_ID)

    check = verify_recovered_answer_payload(
        payload,
        expected_request_id=REQUEST_ID,
    )
    assert check["valid"] is False
    assert "answer_provenance_malformed" in check["issues"]


def test_require_recovered_answer_payload_rejects_invalid_marked_result():
    payload = answer_payload()
    body = dict(payload)
    body.pop("delivery_receipt")
    body["cognition"] = {}
    resealed = seal_chat_delivery_payload(body, request_id=REQUEST_ID)

    with pytest.raises(ValueError, match="chat_recovery_provenance_mismatch"):
        require_recovered_answer_payload(
            resealed,
            expected_request_id=REQUEST_ID,
        )


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
        return NS(data=[self.row])


class Client:
    def __init__(self, row):
        self.row = row
        self.finished = []

    def table(self, name):
        return Query(self.row)

    def rpc(self, name, params):
        self.finished.append((name, params))
        return NS(execute=lambda: NS(data=True))


def test_durable_saved_answer_rechecks_provenance_before_returning():
    payload = answer_payload()
    row = {
        "status": "ready",
        "result": payload,
        "checkpoint": "done",
        "lease_until": None,
        "created_at": "2026-09-24T00:00:00+00:00",
        "updated_at": "2026-09-24T00:00:01+00:00",
    }
    result = TaskStore(Client(row)).get(REQUEST_ID, TOKEN)

    assert result["status"] == "ready"
    assert result["delivery_integrity"]["valid"] is True
    assert result["recovery_integrity"]["valid"] is True
    assert result["recovery_integrity"]["status"] == "verified_production"


def test_durable_recovery_withholds_marked_answer_missing_provenance():
    payload = answer_payload()
    body = dict(payload)
    body.pop("delivery_receipt")
    body["cognition"] = {}
    resealed = seal_chat_delivery_payload(body, request_id=REQUEST_ID)
    row = {
        "status": "ready",
        "result": resealed,
        "checkpoint": "done",
        "lease_until": None,
        "created_at": "2026-09-24T00:00:00+00:00",
        "updated_at": "2026-09-24T00:00:01+00:00",
    }
    result = TaskStore(Client(row)).get(REQUEST_ID, TOKEN)

    assert result["status"] == "failed"
    assert result["result"]["error"] is True
    assert result["recovery_integrity"]["valid"] is False


def test_durable_finish_rechecks_provenance_before_database_write():
    client = Client({})
    store = TaskStore(client)
    payload = answer_payload()
    request = {"request_id": REQUEST_ID, "message": "fixture"}
    digest = request_hash(request)

    assert store.finish_bound(
        REQUEST_ID, "worker", digest, request, payload
    ) is True
    assert client.finished and client.finished[0][0] == "l_task_finish_bound"

    body = dict(payload)
    body.pop("delivery_receipt")
    body["cognition"] = {}
    invalid = seal_chat_delivery_payload(body, request_id=REQUEST_ID)

    with pytest.raises(ValueError, match="chat_recovery_provenance_mismatch"):
        store.finish_bound(
            REQUEST_ID, "worker", digest, request, invalid
        )


def test_real_chat_marks_layer103_protocol(monkeypatch):
    from api import server
    from core.cognition.model_independence import OpenAIChatCompletionsAdapter

    for key, value in production_env().items():
        monkeypatch.setenv(key, value)

    client = NS(
        chat=NS(
            completions=NS(
                create=lambda **kw: NS(
                    id="layer103-fixture",
                    model="fixture-model",
                    choices=[NS(finish_reason="stop", message=NS(content=REPLY))],
                )
            )
        )
    )

    monkeypatch.setattr(
        server,
        "resolve_model_adapter",
        lambda: OpenAIChatCompletionsAdapter(client, model_id="fixture-model"),
    )
    monkeypatch.setattr(
        server,
        "route_capability",
        lambda _: {"handled": False, "status": "not_required"},
    )
    monkeypatch.setattr(
        server,
        "run_cognitive_core",
        lambda message, rhee_packet, **kw: {
            "engine": "project_l_cognitive_core",
            "version": "14.10",
            "runtime": {"status": "complete", "fallback_used": False},
            "controller": kw["cognitive_plan"],
            "route": {"rike": "not_required"},
            "rike": {"status": "not_required", "confidence": {}},
            "guardrails": {"passed": True, "issues": []},
            "working_memory": kw.get("working_memory_packet") or {},
            "model_independence": {},
            "portability": {},
        },
    )
    monkeypatch.setattr(
        server,
        "write_raw_catchall",
        lambda role, content, **kw: {"id": 103, "role": role, "content": content},
    )
    monkeypatch.setattr(
        server,
        "write_live_short_term",
        lambda *args, **kw: {"saved": False, "reason": "fixture"},
    )
    monkeypatch.setattr(server, "run_brain_pipeline", lambda *a, **kw: None)
    monkeypatch.setattr(server, "voice_enabled", lambda: False)

    result = server.chat(
        server.ChatRequest(message="Hello L", request_id=REQUEST_ID)
    )
    check = verify_recovered_answer_payload(
        result,
        expected_request_id=REQUEST_ID,
    )

    assert result[PROTOCOL_KEY] == PROTOCOL_VERSION
    assert result["cognition"]["answer_provenance"]["release_layer"] >= 103
    assert check["valid"] is True
    assert check["status"] == "verified_authentic_production"


def test_server_surfaces_layer103_recovery_readiness():
    from pathlib import Path

    source = Path("api/server.py").read_text(encoding="utf-8")
    assert '"release_layer":' in source
    assert '"recovery_provenance_ready": True' in source
    assert "mark_answer_provenance_required(" in source
    assert "verify_recovered_answer_payload(" in source
