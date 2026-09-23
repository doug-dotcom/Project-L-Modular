"""Layer 101: production provenance attestation."""

import json
from pathlib import Path

from core.cognition.release_provenance import (
    EXPECTED_BRANCH,
    EXPECTED_ENVIRONMENT,
    EXPECTED_REPOSITORY,
    EXPECTED_SERVICE,
    VERSION,
    build_release_provenance,
    verify_release_provenance,
)


COMMIT = "a" * 40


def production_env(**overrides):
    env = {
        "RAILWAY_GIT_REPO_OWNER": "doug-dotcom",
        "RAILWAY_GIT_REPO_NAME": "Project-L-Modular",
        "RAILWAY_GIT_BRANCH": "main",
        "RAILWAY_GIT_COMMIT_SHA": COMMIT,
        "RAILWAY_PROJECT_NAME": "profound-wonder",
        "RAILWAY_SERVICE_NAME": "Project-L-Modular",
        "RAILWAY_ENVIRONMENT_NAME": "production",
        "L_ANSWER_PROVENANCE_SIGNING_KEY": "l" * 64,
        "L_ANSWER_PROVENANCE_ACTIVE_KEY_ID": "k2-2026-09",
        "L_ANSWER_PROVENANCE_VERIFY_KEY_IDS": "k2-2026-09",
        "L_ANSWER_PROVENANCE_SIGNING_KEY_K2_2026_09": "k" * 64,
        "OPENAI_API_KEY": "must-not-leak",
        "SUPABASE_SERVICE_ROLE_KEY": "must-not-leak",
    }
    env.update(overrides)
    return env


def test_production_runtime_identity_builds_verified_self_hashed_receipt():
    receipt = build_release_provenance(production_env())
    check = verify_release_provenance(receipt)

    assert receipt["version"] == VERSION
    assert receipt["status"] == "verified_production"
    assert receipt["verified"] is True
    assert receipt["repository"] == EXPECTED_REPOSITORY
    assert receipt["branch"] == EXPECTED_BRANCH
    assert receipt["service_name"] == EXPECTED_SERVICE
    assert receipt["environment_name"] == EXPECTED_ENVIRONMENT
    assert receipt["commit_sha"] == COMMIT
    assert receipt["metadata_complete"] is True
    assert receipt["commit_sha_valid"] is True
    assert len(receipt["receipt_sha256"]) == 64

    assert check["valid"] is True
    assert check["verified_production"] is True
    assert check["commit_sha"] == COMMIT


def test_receipt_contains_no_secret_environment_values():
    receipt = build_release_provenance(production_env())
    text = json.dumps(receipt)

    assert "must-not-leak" not in text
    assert "OPENAI_API_KEY" not in text
    assert "SUPABASE_SERVICE_ROLE_KEY" not in text
    assert "SUPABASE_URL" not in text


def test_incomplete_local_metadata_is_honestly_unavailable_not_failed():
    receipt = build_release_provenance({})

    assert receipt["status"] == "unavailable"
    assert receipt["verified"] is False
    assert receipt["metadata_complete"] is False
    assert receipt["commit_sha"] == ""
    assert verify_release_provenance(receipt)["valid"] is True


def test_wrong_repository_or_environment_cannot_claim_production():
    wrong_repo = build_release_provenance(
        production_env(RAILWAY_GIT_REPO_NAME="some-other-repo")
    )
    wrong_env = build_release_provenance(
        production_env(RAILWAY_ENVIRONMENT_NAME="staging")
    )

    assert wrong_repo["status"] == "metadata_mismatch"
    assert wrong_repo["verified"] is False
    assert wrong_env["status"] == "metadata_mismatch"
    assert wrong_env["verified"] is False


def test_invalid_commit_sha_blocks_complete_production_attestation():
    receipt = build_release_provenance(
        production_env(RAILWAY_GIT_COMMIT_SHA="not-a-sha")
    )

    assert receipt["status"] == "unavailable"
    assert receipt["verified"] is False
    assert receipt["commit_sha"] == ""
    assert receipt["commit_sha_valid"] is False


def test_tampered_receipt_fails_verification():
    receipt = build_release_provenance(production_env())
    receipt["branch"] = "tampered-branch"

    check = verify_release_provenance(receipt)
    assert check["valid"] is False
    assert "provenance_receipt_hash_mismatch" in check["issues"]
    assert check["commit_sha"] == ""


def test_forged_verified_receipt_with_rehashed_wrong_service_is_rejected():
    receipt = build_release_provenance(production_env())
    receipt["service_name"] = "wrong-service"

    # Simulate an attacker who can recompute the public self-hash but not change
    # the verifier's production identity contract.
    from core.cognition import release_provenance as rp

    payload = dict(receipt)
    payload.pop("receipt_sha256", None)
    receipt["receipt_sha256"] = rp._canonical_sha256(payload)

    check = verify_release_provenance(receipt)
    assert check["valid"] is False
    assert "provenance_service_mismatch" in check["issues"]


def test_provenance_claims_do_not_overreach():
    receipt = build_release_provenance(production_env())

    assert receipt["claims"] == {
        "running_source_identity": "verified",
        "commit_quality": "not_asserted",
        "deployment_health": "not_asserted",
        "answer_quality": "not_asserted",
        "human_acceptance": "not_asserted",
    }


def test_server_exposes_layer101_provenance_surfaces(monkeypatch):
    from api import server

    for key, value in production_env().items():
        monkeypatch.setenv(key, value)

    health = server.health()
    assert health["release_layer"] >= 101
    assert health["release_provenance_ready"] is True
    assert health["release_provenance"]["verified"] is True
    assert health["release_provenance"]["commit_sha"] == COMMIT

    status = server.cognition_status()
    assert status["release_layer"] >= 101
    assert status["release_provenance"]["verified"] is True

    endpoint = server.cognition_release_provenance()
    assert endpoint["verified"] is True
    assert endpoint["verification"]["valid"] is True
    assert endpoint["verification"]["verified_production"] is True


def test_server_source_has_layer101_endpoint_and_not_raw_environment_dump():
    source = Path("api/server.py").read_text(encoding="utf-8")

    assert '"release_layer":' in source
    assert '"release_provenance_ready": True' in source
    assert '@app.get("/cognition/release-provenance")' in source
    assert "build_release_provenance()" in source
    assert "dict(os.environ)" not in source
