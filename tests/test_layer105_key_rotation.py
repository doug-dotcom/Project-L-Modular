"""Layer 105: rotatable HMAC keyring for answer provenance."""

from types import SimpleNamespace as NS

from core.cognition.answer_authenticity import (
    ACTIVE_KEY_ID_ENV,
    KEY_ENV_PREFIX,
    LEGACY_VERSION,
    SIGNING_KEY_ENV,
    VERIFY_KEY_IDS_ENV,
    VERSION,
    authenticity_status,
    sign_answer_provenance,
    verify_answer_authenticity,
)
from core.cognition.answer_provenance import build_answer_provenance
from core.cognition.delivery_integrity import seal_chat_delivery_payload
from core.cognition.production_baseline import summarise_production_baseline
from core.cognition.recovery_provenance import (
    PROTOCOL_KEY,
    PROTOCOL_VERSION,
    mark_answer_provenance_required,
    verify_recovered_answer_payload,
)
from core.cognition.release_provenance import build_release_provenance


REQUEST_ID = "00000000-0000-4000-8000-000000000105"
COMMIT = "e" * 40
REPLY = "Layer 105 rotated-key answer."
LEGACY_KEY = "L" * 64
K2 = "2" * 64
K3 = "3" * 64
K2_ID = "k2-2026-09"
K3_ID = "k3-2026-10"


def key_env(key_id):
    return KEY_ENV_PREFIX + key_id.upper().replace("-", "_")


def runtime_env(*, active=K2_ID, verify=None, include_k2=True, include_k3=False):
    env = {
        "RAILWAY_GIT_REPO_OWNER": "doug-dotcom",
        "RAILWAY_GIT_REPO_NAME": "Project-L-Modular",
        "RAILWAY_GIT_BRANCH": "main",
        "RAILWAY_GIT_COMMIT_SHA": COMMIT,
        "RAILWAY_PROJECT_NAME": "profound-wonder",
        "RAILWAY_SERVICE_NAME": "Project-L-Modular",
        "RAILWAY_ENVIRONMENT_NAME": "production",
        SIGNING_KEY_ENV: LEGACY_KEY,
        ACTIVE_KEY_ID_ENV: active,
        VERIFY_KEY_IDS_ENV: verify if verify is not None else active,
    }
    if include_k2:
        env[key_env(K2_ID)] = K2
    if include_k3:
        env[key_env(K3_ID)] = K3
    return env


def provenance(env):
    release = build_release_provenance(env)
    model = {"status": "complete", "model_id": "fixture-model"}
    context = {"version": "1.0", "mode": "lean", "rendered_chars": 900}
    persistence = {"version": "1.0", "status": "verified", "valid": True}
    answer = build_answer_provenance(
        request_id=REQUEST_ID,
        final_reply=REPLY,
        release_provenance=release,
        model_receipt=model,
        context_budget=context,
        assistant_persistence=persistence,
        release_layer=105,
    )
    return answer, release, model, context, persistence


def test_keyring_signs_new_answers_with_active_nonsecret_key_id():
    env = runtime_env()
    answer, *_ = provenance(env)

    signed = sign_answer_provenance(answer, environ=env)
    check = verify_answer_authenticity(signed, answer, environ=env)

    assert signed["version"] == VERSION
    assert signed["key_id"] == K2_ID
    assert signed["valid"] is True
    assert len(signed["signature"]) == 64
    assert K2 not in str(signed)
    assert LEGACY_KEY not in str(signed)

    assert check["valid"] is True
    assert check["authentic"] is True
    assert check["verification_mode"] == "keyring"
    assert check["key_id"] == K2_ID


def test_layer104_legacy_signature_remains_verifiable_after_rotation():
    env = runtime_env()
    answer, *_ = provenance(env)

    legacy = sign_answer_provenance(answer, signing_key=LEGACY_KEY)
    check = verify_answer_authenticity(legacy, answer, environ=env)

    assert legacy["version"] == LEGACY_VERSION
    assert "key_id" not in legacy
    assert check["valid"] is True
    assert check["verification_mode"] == "legacy_layer104"
    assert check["key_id"] == ""


def test_rotation_overlap_verifies_old_key_and_signs_new_key():
    before = runtime_env(active=K2_ID, verify=f"{K2_ID},{K3_ID}", include_k2=True, include_k3=True)
    answer, *_ = provenance(before)
    old_signed = sign_answer_provenance(answer, environ=before)
    assert old_signed["key_id"] == K2_ID

    after = runtime_env(active=K3_ID, verify=f"{K2_ID},{K3_ID}", include_k2=True, include_k3=True)
    new_signed = sign_answer_provenance(answer, environ=after)

    assert new_signed["key_id"] == K3_ID
    assert verify_answer_authenticity(old_signed, answer, environ=after)["valid"] is True
    assert verify_answer_authenticity(new_signed, answer, environ=after)["valid"] is True


def test_retired_key_id_is_rejected_even_if_secret_still_exists():
    overlap = runtime_env(active=K3_ID, verify=f"{K2_ID},{K3_ID}", include_k2=True, include_k3=True)
    answer, *_ = provenance(overlap)

    k2_env = runtime_env(active=K2_ID, verify=f"{K2_ID},{K3_ID}", include_k2=True, include_k3=True)
    old_signed = sign_answer_provenance(answer, environ=k2_env)
    assert old_signed["key_id"] == K2_ID

    retired = runtime_env(active=K3_ID, verify=K3_ID, include_k2=True, include_k3=True)
    check = verify_answer_authenticity(old_signed, answer, environ=retired)

    assert check["valid"] is False
    assert "answer_authenticity_key_id_not_retained" in check["issues"]


def test_missing_active_key_fails_signing_without_falling_back_to_legacy():
    env = runtime_env(active=K3_ID, verify=K3_ID, include_k2=True, include_k3=False)
    answer, *_ = provenance(env)

    signed = sign_answer_provenance(answer, environ=env)
    status = authenticity_status(environ=env)

    assert signed["version"] == VERSION
    assert signed["key_id"] == K3_ID
    assert signed["valid"] is False
    assert signed["signature"] == ""
    assert "signing_key_unavailable" in signed["issues"]
    assert status["active_key_id"] == K3_ID
    assert status["active_key_configured"] is False
    assert status["legacy_verification_configured"] is True


def test_status_exposes_ids_and_readiness_but_never_secrets():
    env = runtime_env(
        active=K3_ID,
        verify=f"{K2_ID},{K3_ID}",
        include_k2=True,
        include_k3=True,
    )
    status = authenticity_status(environ=env)
    text = str(status)

    assert status["mode"] == "keyring"
    assert status["active_key_id"] == K3_ID
    assert status["active_key_configured"] is True
    assert status["retained_key_ids"] == [K2_ID, K3_ID]
    assert status["legacy_verification_configured"] is True
    assert status["rotation_ready"] is True
    assert status["secret_exposed"] is False
    assert K2 not in text
    assert K3 not in text
    assert LEGACY_KEY not in text


def test_production_baseline_counts_verified_signing_key_ids(monkeypatch):
    env = runtime_env()
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    answer, release, model, context, persistence = provenance(env)
    auth = sign_answer_provenance(answer, environ=env)
    payload = {
        "reply": REPLY,
        "server": "vx",
        "cognition": {
            "version": "14.10",
            "runtime": {"status": "complete", "fallback_used": False},
            "model_receipt": model,
            "context_budget": context,
            "assistant_persistence": persistence,
            "release_provenance": release,
            "answer_provenance": answer,
            "answer_authenticity": auth,
            "evidence_evaluation": {"status": "not_checked"},
        },
    }
    payload = mark_answer_provenance_required(payload, protocol_version=PROTOCOL_VERSION)
    payload = seal_chat_delivery_payload(payload, request_id=REQUEST_ID)

    report = summarise_production_baseline([{
        "request_id": REQUEST_ID,
        "created_at": "2026-09-24T00:00:00+00:00",
        "updated_at": "2026-09-24T00:00:01+00:00",
        "status": "ready",
        "result": payload,
    }])
    cohort = report["cohorts"][0]

    assert cohort["answer_authenticity_keys"][K2_ID] == 1
    assert report["answer_quality"]["status"] == "not_scored"


def test_real_chat_uses_active_keyring_id_in_verified_production(monkeypatch):
    from api import server
    from core.cognition.model_independence import OpenAIChatCompletionsAdapter

    env = runtime_env()
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    client = NS(
        chat=NS(
            completions=NS(
                create=lambda **kw: NS(
                    id="layer105-fixture",
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
        lambda role, content, **kw: {"id": 105, "role": role, "content": content},
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
    auth = result["cognition"]["answer_authenticity"]
    check = verify_recovered_answer_payload(
        result,
        expected_request_id=REQUEST_ID,
    )

    assert result[PROTOCOL_KEY] == PROTOCOL_VERSION
    assert result["cognition"]["answer_provenance"]["release_layer"] == 105
    assert auth["version"] == VERSION
    assert auth["key_id"] == K2_ID
    assert auth["valid"] is True
    assert check["valid"] is True
    assert check["answer_authenticity"]["key_id"] == K2_ID


def test_server_surfaces_layer105_keyring_without_secret_names():
    from pathlib import Path

    source = Path("api/server.py").read_text(encoding="utf-8")
    assert '"release_layer": 105' in source
    assert '"answer_authenticity": authenticity_status()' in source
    assert "L_ANSWER_PROVENANCE_SIGNING_KEY_K2_2026_09" not in source
    assert K2 not in source
