"""Layer 100 milestone: release certification and claim boundaries."""

import json
from pathlib import Path

from core.cognition.release_certification import (
    LAYER,
    VERSION,
    build_release_certification,
)


def test_layer100_release_certification_executes_all_runtime_contracts():
    report = build_release_certification()

    assert LAYER == 100
    assert VERSION == "layer100-release-certification-1"
    assert report["layer"] == 100
    assert report["milestone"] == "project_l_100_layers"
    assert report["status"] == "verified"
    assert report["verified"] is True
    assert len(report["checks"]) == 5
    assert all(item["passed"] for item in report["checks"])

    by_name = {item["name"]: item for item in report["checks"]}
    assert by_name["publication_delivery_integrity"]["evidence"]["delivery_bound"] is True
    assert by_name["bounded_cognition_failsafe"]["evidence"]["exception_message_hidden"] is True
    assert by_name["adaptive_context_budget"]["evidence"]["marker_removed"] is True
    assert by_name["adaptive_context_budget"]["evidence"]["rhee_evidence_modified"] is False
    assert by_name["bounded_quality_trial_contract"]["evidence"]["planned_calls"] == 8
    assert by_name["production_baseline_honesty"]["evidence"]["answer_quality_status"] == "not_scored"


def test_certification_does_not_self_award_live_or_human_acceptance():
    report = build_release_certification()
    claims = report["claims"]

    assert claims["runtime_integrity_self_check"] == "verified"
    for key in (
        "production_deployment",
        "live_model_quality",
        "private_memory_recall_quality",
        "phone_acceptance",
        "human_conversation_review",
    ):
        assert claims[key] == "not_asserted_by_self_check"

    assert set(report["human_acceptance_required"]) == {
        "live model quality",
        "private-memory recall quality",
        "conversation quality",
        "physical-phone UX",
    }
    text = json.dumps(report).lower()
    assert "intelligence score" in text
    assert "does not prove railway deployment state" in text


def test_certification_receipts_do_not_expose_synthetic_secret_or_reply_text():
    report = build_release_certification()
    text = json.dumps(report)

    assert "layer100-secret-error-detail" not in text
    assert "Layer 100 synthetic publication integrity check." not in text
    assert "LAYER100-INACTIVE-CONTEXT-MARKER" not in text


def test_server_exposes_layer100_health_status_and_certification_endpoint():
    source = Path("api/server.py").read_text(encoding="utf-8")

    # Layer 100 is a durable milestone contract, not a permanent current-release number.
    assert '"release_layer":' in source
    assert '"release_certification_ready": True' in source
    assert '@app.get("/cognition/release-certification")' in source
    assert "return build_release_certification()" in source
    assert '"release_certification": build_release_certification()' in source


def test_direct_server_certification_matches_layer100_contract():
    from api import server

    report = server.cognition_release_certification()
    assert report["verified"] is True
    assert report["layer"] == 100

    health = server.health()
    assert health["release_layer"] >= 100
    assert health["release_certification_ready"] is True
