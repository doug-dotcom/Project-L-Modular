"""Layer 107: production cryptographic readiness gate."""

from fastapi.responses import JSONResponse

from core.cognition.answer_authenticity import (
    ACTIVE_KEY_ID_ENV,
    KEY_ENV_PREFIX,
    SIGNING_KEY_ENV,
    VERIFY_KEY_IDS_ENV,
)
from core.cognition.production_security_gate import (
    RELEASE_LAYER,
    VERSION,
    production_security_gate,
)


COMMIT = "7" * 40
ACTIVE = "k2-2026-09"
LEGACY = "L" * 64
ACTIVE_KEY = "K" * 64


def key_env_name(key_id):
    return KEY_ENV_PREFIX + key_id.upper().replace("-", "_")


def production_env(**overrides):
    env = {
        "RAILWAY_GIT_REPO_OWNER": "doug-dotcom",
        "RAILWAY_GIT_REPO_NAME": "Project-L-Modular",
        "RAILWAY_GIT_BRANCH": "main",
        "RAILWAY_GIT_COMMIT_SHA": COMMIT,
        "RAILWAY_PROJECT_NAME": "profound-wonder",
        "RAILWAY_SERVICE_NAME": "Project-L-Modular",
        "RAILWAY_ENVIRONMENT_NAME": "production",
        SIGNING_KEY_ENV: LEGACY,
        ACTIVE_KEY_ID_ENV: ACTIVE,
        VERIFY_KEY_IDS_ENV: ACTIVE,
        key_env_name(ACTIVE): ACTIVE_KEY,
    }
    env.update(overrides)
    return env


def test_verified_production_passes_full_keyring_self_test():
    report = production_security_gate(production_env())

    assert VERSION == "layer107-production-security-gate-1"
    assert RELEASE_LAYER == 107
    assert report["production_enforced"] is True
    assert report["ready"] is True
    assert report["status"] == "ready"
    assert report["release_commit_sha"] == COMMIT
    assert report["active_key_id"] == ACTIVE
    assert report["explicit_verify_key_ids"] == [ACTIVE]
    assert report["checks"]["keyring_mode"] is True
    assert report["checks"]["active_key_configured"] is True
    assert report["checks"]["active_key_explicitly_retained"] is True
    assert report["checks"]["legacy_verification_configured"] is True
    assert report["self_test"]["attempted"] is True
    assert report["self_test"]["signed"] is True
    assert report["self_test"]["verified"] is True
    assert report["self_test"]["key_id"] == ACTIVE
    assert report["issues"] == []


def test_missing_active_secret_blocks_verified_production():
    env = production_env()
    env.pop(key_env_name(ACTIVE))

    report = production_security_gate(env)

    assert report["production_enforced"] is True
    assert report["ready"] is False
    assert report["status"] == "blocked"
    assert "production_active_key_secret_required" in report["issues"]
    assert "production_signing_self_test_failed" in report["issues"]
    assert "production_verification_self_test_failed" in report["issues"]


def test_active_key_must_be_explicitly_in_verify_list():
    report = production_security_gate(
        production_env(**{VERIFY_KEY_IDS_ENV: "some-other-key"})
    )

    assert report["ready"] is False
    assert "production_active_key_must_be_in_verify_list" in report["issues"]


def test_missing_legacy_verification_key_blocks_current_rotation_contract():
    env = production_env()
    env.pop(SIGNING_KEY_ENV)

    report = production_security_gate(env)

    assert report["ready"] is False
    assert "production_legacy_verification_key_required" in report["issues"]


def test_nonproduction_runtime_is_observable_but_not_health_blocking():
    env = production_env(RAILWAY_ENVIRONMENT_NAME="staging")
    report = production_security_gate(env)

    assert report["production_enforced"] is False
    assert report["ready"] is True
    assert report["status"] == "not_enforced_nonproduction"
    assert report["self_test"]["attempted"] is False


def test_security_report_never_exposes_signing_secrets():
    env = production_env()
    report = production_security_gate(env)
    text = str(report)

    assert LEGACY not in text
    assert ACTIVE_KEY not in text
    assert report["privacy"]["secret_values_returned"] is False
    assert report["privacy"]["signatures_returned"] is False


def test_server_health_is_200_shape_when_crypto_ready(monkeypatch):
    from api import server

    for key, value in production_env().items():
        monkeypatch.setenv(key, value)

    result = server.health()

    assert isinstance(result, dict)
    assert result["status"] == "ok"
    assert result["release_layer"] == 107
    assert result["production_security_gate"]["ready"] is True
    assert result["production_security_gate"]["production_enforced"] is True


def test_server_health_returns_503_when_verified_production_crypto_is_broken(monkeypatch):
    from api import server

    env = production_env()
    env.pop(key_env_name(ACTIVE))
    for key in list(production_env()):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    result = server.health()

    assert isinstance(result, JSONResponse)
    assert result.status_code == 503
    assert b'"status":"blocked"' in result.body
    assert b'"production_active_key_secret_required"' in result.body
    assert ACTIVE_KEY.encode() not in result.body
    assert LEGACY.encode() not in result.body


def test_security_readiness_endpoint_matches_gate(monkeypatch):
    from api import server

    for key, value in production_env().items():
        monkeypatch.setenv(key, value)

    result = server.cognition_security_readiness()

    assert result["version"] == VERSION
    assert result["ready"] is True
    assert result["active_key_id"] == ACTIVE
    assert result["claims"]["answer_quality"] == "not_asserted"


def test_server_source_wires_layer107_into_health():
    from pathlib import Path

    source = Path("api/server.py").read_text(encoding="utf-8")
    assert '"release_layer": 107' in source
    assert "security_gate = production_security_gate()" in source
    assert "return JSONResponse(payload, status_code=503)" in source
    assert '@app.get("/cognition/security-readiness")' in source
    assert "production_security_gate()" in source
