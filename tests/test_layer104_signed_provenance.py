"""Layer 104: HMAC-authenticated answer provenance."""

from types import SimpleNamespace as NS

from core.cognition.answer_authenticity import (
    ALGORITHM,
    SIGNING_KEY_ENV,
    authenticity_status,
    sign_answer_provenance,
    verify_answer_authenticity,
)
from core.cognition.answer_provenance import build_answer_provenance
from core.cognition.delivery_integrity import seal_chat_delivery_payload
from core.cognition.recovery_provenance import (
    LEGACY_PROTOCOL_VERSION,
    PROTOCOL_KEY,
    PROTOCOL_VERSION,
    mark_answer_provenance_required,
    verify_recovered_answer_payload,
)
from core.cognition.release_provenance import build_release_provenance


REQUEST_ID = "00000000-0000-4000-8000-000000000104"
COMMIT = "d" * 40
REPLY = "Layer 104 signed answer."
KEY = "K" * 64
WRONG_KEY = "W" * 64


def production_env(signing_key=KEY):
    return {
        "RAILWAY_GIT_REPO_OWNER": "doug-dotcom",
        "RAILWAY_GIT_REPO_NAME": "Project-L-Modular",
        "RAILWAY_GIT_BRANCH": "main",
        "RAILWAY_GIT_COMMIT_SHA": COMMIT,
        "RAILWAY_PROJECT_NAME": "profound-wonder",
        "RAILWAY_SERVICE_NAME": "Project-L-Modular",
        "RAILWAY_ENVIRONMENT_NAME": "production",
        SIGNING_KEY_ENV: signing_key,
    }


def provenance():
    release = build_release_provenance(production_env())
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
        release_layer=104,
    )
    return answer, release, model, context, persistence


def signed_payload(*, signing_key=KEY, protocol=PROTOCOL_VERSION):
    answer, release, model, context, persistence = provenance()
    authenticity = sign_answer_provenance(answer, signing_key=signing_key)
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
        protocol_version=protocol,
    )
    return seal_chat_delivery_payload(body, request_id=REQUEST_ID)


def test_hmac_signature_verifies_with_server_key_only():
    answer, *_ = provenance()
    signed = sign_answer_provenance(answer, signing_key=KEY)

    assert signed["valid"] is True
    assert signed["status"] == "signed"
    assert signed["algorithm"] == ALGORITHM
    assert len(signed["signature"]) == 64
    assert KEY not in str(signed)

    check = verify_answer_authenticity(
        signed,
        answer,
        signing_key=KEY,
    )
    assert check["valid"] is True
    assert check["authentic"] is True


def test_wrong_key_cannot_verify_signature():
    answer, *_ = provenance()
    signed = sign_answer_provenance(answer, signing_key=KEY)

    check = verify_answer_authenticity(
        signed,
        answer,
        signing_key=WRONG_KEY,
    )
    assert check["valid"] is False
    assert "answer_authenticity_signature_mismatch" in check["issues"]


def test_public_rehash_after_tampering_cannot_forge_hmac():
    answer, *_ = provenance()
    signed = sign_answer_provenance(answer, signing_key=KEY)

    changed = dict(answer)
    changed["release_commit_sha"] = "e" * 40

    from core.cognition import answer_provenance as ap

    body = dict(changed)
    body.pop("receipt_sha256")
    changed["receipt_sha256"] = ap._canonical_sha256(body)

    # Public self-hash is internally consistent again, but the original HMAC
    # cannot authenticate the rewritten provenance.
    check = verify_answer_authenticity(
        signed,
        changed,
        signing_key=KEY,
    )
    assert check["valid"] is False
    assert (
        "answer_authenticity_provenance_receipt_mismatch" in check["issues"]
        or "answer_authenticity_payload_hash_mismatch" in check["issues"]
        or "answer_authenticity_signature_mismatch" in check["issues"]
    )


def test_missing_or_short_signing_key_never_creates_fake_signature():
    answer, *_ = provenance()

    missing = sign_answer_provenance(answer, signing_key="")
    short = sign_answer_provenance(answer, signing_key="short")

    assert missing["valid"] is False
    assert missing["status"] == "unavailable"
    assert missing["signature"] == ""
    assert short["valid"] is False
    assert authenticity_status("")["configured"] is False
    assert authenticity_status(KEY)["configured"] is True


def test_protocol_v2_requires_authenticity_but_v1_history_remains_readable(monkeypatch):
    monkeypatch.setenv(SIGNING_KEY_ENV, KEY)

    v2 = signed_payload()
    v2_check = verify_recovered_answer_payload(
        v2,
        expected_request_id=REQUEST_ID,
    )
    assert v2[PROTOCOL_KEY] == PROTOCOL_VERSION
    assert v2_check["valid"] is True
    assert v2_check["status"] == "verified_authentic_production"
    assert v2_check["authenticity_required"] is True
    assert v2_check["answer_authenticity"]["authentic"] is True

    # Remove authenticity, then reseal the public delivery hash: v2 still fails.
    body = dict(v2)
    body.pop("delivery_receipt")
    cognition = dict(body["cognition"])
    cognition.pop("answer_authenticity")
    body["cognition"] = cognition
    no_auth = seal_chat_delivery_payload(body, request_id=REQUEST_ID)
    no_auth_check = verify_recovered_answer_payload(
        no_auth,
        expected_request_id=REQUEST_ID,
    )
    assert no_auth_check["valid"] is False
    assert "answer_authenticity_required_but_missing" in no_auth_check["issues"]

    # Layer 103 protocol-v1 remains a compatibility path.
    answer, release, model, context, persistence = provenance()
    legacy = {
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
    legacy = mark_answer_provenance_required(
        legacy,
        protocol_version=LEGACY_PROTOCOL_VERSION,
    )
    legacy = seal_chat_delivery_payload(legacy, request_id=REQUEST_ID)
    legacy_check = verify_recovered_answer_payload(
        legacy,
        expected_request_id=REQUEST_ID,
    )
    assert legacy_check["valid"] is True
    assert legacy_check["status"] == "verified_production"
    assert legacy_check["authenticity_required"] is False


def test_protocol_v2_wrong_runtime_secret_fails_recovery(monkeypatch):
    payload = signed_payload(signing_key=KEY)
    monkeypatch.setenv(SIGNING_KEY_ENV, WRONG_KEY)

    check = verify_recovered_answer_payload(
        payload,
        expected_request_id=REQUEST_ID,
    )
    assert check["valid"] is False
    assert "answer_authenticity_verification_failed" in check["issues"]
    assert "answer_authenticity_signature_mismatch" in check["answer_authenticity"]["issues"]


def test_real_chat_emits_signed_protocol_v2_in_verified_production(monkeypatch):
    from api import server
    from core.cognition.model_independence import OpenAIChatCompletionsAdapter

    for key, value in production_env().items():
        monkeypatch.setenv(key, value)

    client = NS(
        chat=NS(
            completions=NS(
                create=lambda **kw: NS(
                    id="layer104-fixture",
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
        lambda role, content, **kw: {"id": 104, "role": role, "content": content},
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

    assert result["reply"] == REPLY
    assert result[PROTOCOL_KEY] == PROTOCOL_VERSION
    assert result["cognition"]["answer_provenance"]["release_layer"] >= 104
    assert result["cognition"]["answer_authenticity"]["valid"] is True
    assert result["cognition"]["answer_authenticity"]["signature"]
    assert check["valid"] is True
    assert check["status"] == "verified_authentic_production"


def test_server_exposes_layer104_authenticity_readiness():
    from pathlib import Path

    source = Path("api/server.py").read_text(encoding="utf-8")
    assert '"release_layer":' in source
    assert '"answer_authenticity": authenticity_status()' in source
    assert "sign_answer_provenance(answer_provenance)" in source
    assert "verify_answer_authenticity(" in source
    assert SIGNING_KEY_ENV not in source
