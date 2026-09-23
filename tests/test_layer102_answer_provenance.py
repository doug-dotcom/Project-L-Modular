"""Layer 102: bind completed answers to exact runtime release provenance."""

import json
from types import SimpleNamespace as NS

from core.cognition.answer_provenance import (
    RELEASE_LAYER,
    build_answer_provenance,
    verify_answer_provenance,
)
from core.cognition.delivery_integrity import seal_chat_delivery_payload
from core.cognition.production_baseline import summarise_production_baseline
from core.cognition.release_provenance import build_release_provenance


COMMIT = "b" * 40
REPLY = "Synthetic Layer 102 answer."


def production_env():
    return {
        "RAILWAY_GIT_REPO_OWNER": "doug-dotcom",
        "RAILWAY_GIT_REPO_NAME": "Project-L-Modular",
        "RAILWAY_GIT_BRANCH": "main",
        "RAILWAY_GIT_COMMIT_SHA": COMMIT,
        "RAILWAY_PROJECT_NAME": "profound-wonder",
        "RAILWAY_SERVICE_NAME": "Project-L-Modular",
        "RAILWAY_ENVIRONMENT_NAME": "production",
    }


def components():
    release = build_release_provenance(production_env())
    model = {
        "status": "complete",
        "model_id": "fixture-model",
        "provider_response": {"response_id": "fixture"},
    }
    context = {
        "version": "1.0",
        "mode": "lean",
        "rendered_chars": 1200,
        "receipt_sha256": "c" * 64,
    }
    persistence = {
        "version": "1.0",
        "status": "verified",
        "valid": True,
        "receipt_sha256": "d" * 64,
    }
    return release, model, context, persistence


def build_receipt(request_id="req-102", reply=REPLY):
    release, model, context, persistence = components()
    receipt = build_answer_provenance(
        request_id=request_id,
        final_reply=reply,
        release_provenance=release,
        model_receipt=model,
        context_budget=context,
        assistant_persistence=persistence,
    )
    return receipt, release, model, context, persistence


def test_answer_provenance_binds_reply_request_release_and_runtime_receipts():
    receipt, release, model, context, persistence = build_receipt()
    check = verify_answer_provenance(
        receipt,
        request_id="req-102",
        final_reply=REPLY,
        release_provenance=release,
        model_receipt=model,
        context_budget=context,
        assistant_persistence=persistence,
    )

    assert RELEASE_LAYER == 102
    assert receipt["status"] == "verified_production"
    assert receipt["verified"] is True
    assert receipt["release_layer"] == 102
    assert receipt["release_commit_sha"] == COMMIT
    assert len(receipt["reply_sha256"]) == 64
    assert len(receipt["receipt_sha256"]) == 64
    assert check["valid"] is True
    assert check["verified_production"] is True
    assert check["release_commit_sha"] == COMMIT


def test_answer_provenance_never_duplicates_reply_or_private_runtime_content():
    secret_reply = "PRIVATE ANSWER TEXT MUST NOT APPEAR"
    release, model, context, persistence = components()
    model["secret"] = "PRIVATE MODEL DETAIL"
    receipt = build_answer_provenance(
        request_id="req-private",
        final_reply=secret_reply,
        release_provenance=release,
        model_receipt=model,
        context_budget=context,
        assistant_persistence=persistence,
    )
    text = json.dumps(receipt)

    assert secret_reply not in text
    assert "PRIVATE MODEL DETAIL" not in text
    assert receipt["reply_sha256"]
    assert receipt["response_model_receipt_sha256"]


def test_changed_reply_request_or_bound_receipt_fails_verification():
    receipt, release, model, context, persistence = build_receipt()

    wrong_reply = verify_answer_provenance(
        receipt,
        request_id="req-102",
        final_reply="changed answer",
        release_provenance=release,
        model_receipt=model,
        context_budget=context,
        assistant_persistence=persistence,
    )
    assert "answer_provenance_reply_hash_mismatch" in wrong_reply["issues"]

    wrong_request = verify_answer_provenance(
        receipt,
        request_id="different-request",
        final_reply=REPLY,
        release_provenance=release,
        model_receipt=model,
        context_budget=context,
        assistant_persistence=persistence,
    )
    assert "answer_provenance_request_id_mismatch" in wrong_request["issues"]

    changed_model = dict(model)
    changed_model["model_id"] = "different-model"
    wrong_model = verify_answer_provenance(
        receipt,
        request_id="req-102",
        final_reply=REPLY,
        release_provenance=release,
        model_receipt=changed_model,
        context_budget=context,
        assistant_persistence=persistence,
    )
    assert "response_model_receipt_mismatch" in wrong_model["issues"]


def test_rehashed_forgery_cannot_swap_release_commit():
    receipt, release, model, context, persistence = build_receipt()
    receipt["release_commit_sha"] = "e" * 40

    from core.cognition import answer_provenance as ap

    payload = dict(receipt)
    payload.pop("receipt_sha256")
    receipt["receipt_sha256"] = ap._canonical_sha256(payload)

    check = verify_answer_provenance(
        receipt,
        request_id="req-102",
        final_reply=REPLY,
        release_provenance=release,
        model_receipt=model,
        context_budget=context,
        assistant_persistence=persistence,
    )
    assert check["valid"] is False
    assert "answer_provenance_release_commit_mismatch" in check["issues"]


def test_local_runtime_can_be_valid_without_claiming_verified_production():
    release = build_release_provenance({})
    receipt = build_answer_provenance(
        request_id="local-102",
        final_reply=REPLY,
        release_provenance=release,
        model_receipt={},
        context_budget={},
        assistant_persistence={},
    )
    check = verify_answer_provenance(
        receipt,
        request_id="local-102",
        final_reply=REPLY,
        release_provenance=release,
        model_receipt={},
        context_budget={},
        assistant_persistence={},
    )

    assert receipt["status"] == "runtime_unverified"
    assert receipt["verified"] is False
    assert check["valid"] is True
    assert check["verified_production"] is False


def test_production_baseline_groups_verified_answers_by_release_commit():
    receipt, release, model, context, persistence = build_receipt()
    payload = seal_chat_delivery_payload(
        {
            "reply": REPLY,
            "server": "vx",
            "cognition": {
                "version": "14.10",
                "runtime": {"status": "complete", "fallback_used": False},
                "model_receipt": model,
                "context_budget": context,
                "assistant_persistence": persistence,
                "release_provenance": release,
                "answer_provenance": receipt,
                "evidence_evaluation": {"status": "not_checked"},
            },
        },
        request_id="req-102",
    )
    rows = [{
        "request_id": "req-102",
        "created_at": "2026-09-24T00:00:00+00:00",
        "updated_at": "2026-09-24T00:00:01+00:00",
        "status": "ready",
        "result": payload,
    }]

    report = summarise_production_baseline(rows)
    cohort = report["cohorts"][0]

    assert cohort["answer_provenance"]["verified_production"] == 1
    assert cohort["release_commits"][COMMIT] == 1
    assert report["answer_quality"]["status"] == "not_scored"


def test_real_chat_payload_retains_verified_answer_provenance(monkeypatch):
    from api import server
    from core.cognition.model_independence import OpenAIChatCompletionsAdapter

    for key, value in production_env().items():
        monkeypatch.setenv(key, value)

    reply = "Layer 102 fixture response."
    client = NS(
        chat=NS(
            completions=NS(
                create=lambda **kw: NS(
                    id="layer102-fixture",
                    model="fixture-model",
                    choices=[NS(finish_reason="stop", message=NS(content=reply))],
                )
            )
        )
    )

    class Adapter(OpenAIChatCompletionsAdapter):
        pass

    monkeypatch.setattr(
        server,
        "resolve_model_adapter",
        lambda: Adapter(client, model_id="fixture-model"),
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
        lambda role, content, **kw: {"id": 102, "role": role, "content": content},
    )
    monkeypatch.setattr(
        server,
        "write_live_short_term",
        lambda *args, **kw: {"saved": False, "reason": "fixture"},
    )
    monkeypatch.setattr(server, "run_brain_pipeline", lambda *a, **kw: None)
    monkeypatch.setattr(server, "voice_enabled", lambda: False)

    result = server.chat(
        server.ChatRequest(message="Hello L", request_id="00000000-0000-4000-8000-000000000102")
    )

    provenance = result["cognition"]["answer_provenance"]
    verification = result["cognition"]["answer_provenance_verification"]
    release = result["cognition"]["release_provenance"]

    assert result["reply"] == reply
    assert provenance["release_layer"] >= 102
    assert provenance["release_commit_sha"] == COMMIT
    assert provenance["verified"] is True
    assert verification["valid"] is True
    assert verification["verified_production"] is True
    assert release["commit_sha"] == COMMIT


def test_server_surfaces_layer102_answer_provenance_readiness():
    from pathlib import Path

    source = Path("api/server.py").read_text(encoding="utf-8")
    assert '"release_layer":' in source
    assert '"answer_provenance_ready": True' in source
    assert '"answer_provenance": cognitive_packet.get("answer_provenance", {})' in source
    assert '"release_provenance": cognitive_packet.get("release_provenance", {})' in source
