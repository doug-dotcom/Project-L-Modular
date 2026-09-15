from core.cognition.controller import plan_cognition
from core.cognition.personal_research import (
    build_personal_research_packet,
    personal_research_requested,
)


def test_research_brief_language_earns_memory_and_external_evidence():
    plan = plan_cognition("Build me an evolving research brief on this topic")
    assert plan["problem_type"] == "personal_research"
    assert plan["needs"]["personal_research"] is True
    assert plan["needs"]["memory"] is True
    assert plan["needs"]["external_evidence"] is True
    assert plan["needs"]["structured_reasoning"] is True


def test_what_do_we_know_so_far_is_personal_research():
    assert personal_research_requested("What do we know so far about this?") is True


def test_prior_evidence_is_carried_into_the_brief():
    context = "\n".join([
        "92 | memory_research | ID=7 | SOURCE_ROLE=USER | CREATED_AT=2026-09-01T00:00:00+00:00",
        "88 | memory_general | ID=8 | SOURCE_ROLE=USER | CREATED_AT=2026-09-10T00:00:00+00:00",
    ])
    packet = build_personal_research_packet(
        "Update my research brief",
        context,
        {"allowed_claim_modes": ["fact", "inference", "unknown"]},
        {},
    )
    assert packet["active"] is True
    assert packet["status"] == "ready"
    assert len(packet["known_evidence"]) == 2
    assert packet["changes"]


def test_missing_evidence_remains_an_explicit_gap():
    packet = build_personal_research_packet(
        "What do we still need to know?",
        "",
        {"allowed_claim_modes": ["unknown"]},
        {},
    )
    assert packet["status"] == "evidence_gap"
    assert packet["unknowns"]
    assert packet["next_evidence"]


def test_failed_external_capability_cannot_become_current_fact():
    packet = build_personal_research_packet(
        "Update the research",
        "90 | memory_research | ID=1 | SOURCE_ROLE=USER",
        {"allowed_claim_modes": ["inference", "unknown"]},
        {"handled": True, "status": "error"},
    )
    assert any("external/current evidence" in item for item in packet["unknowns"])
    assert packet["governance"]["model_conclusions_are_facts"] is False


def test_ordinary_conversation_does_not_activate_research_layer():
    packet = build_personal_research_packet("Tell me a joke", "", {}, {})
    assert packet["active"] is False
    assert packet["status"] == "not_required"
