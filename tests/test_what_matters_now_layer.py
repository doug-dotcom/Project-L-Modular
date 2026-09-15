from core.cognition.controller import plan_cognition
from core.cognition.what_matters_now import (
    build_what_matters_now_packet,
    what_matters_now_requested,
)


def test_what_matters_now_request_earns_memory_and_structured_reasoning():
    plan = plan_cognition("L what matters most right now?")
    assert plan["problem_type"] == "what_matters_now"
    assert plan["needs"]["memory"] is True
    assert plan["needs"]["structured_reasoning"] is True
    assert plan["needs"]["longitudinal_reasoning"] is True
    assert plan["needs"]["what_matters_now"] is True


def test_natural_priority_language_is_detected():
    assert what_matters_now_requested("What should I focus on now?") is True
    assert what_matters_now_requested("What deserves my attention?") is True
    assert what_matters_now_requested("Tell me a joke") is False


def test_explicit_unfinished_thread_is_highest_priority():
    packet = build_what_matters_now_packet(
        "What matters now?",
        {"unresolved_questions": ["Finish the Project L release"]},
        {},
        {},
        {},
        {},
        {},
        {"claim_policy": {"fact_allowed": True}},
    )
    assert packet["active"] is True
    assert packet["priorities"][0]["kind"] == "unfinished_commitment"
    assert packet["priorities"][0]["text"] == "Finish the Project L release"


def test_layer_never_surfaces_more_than_three_priorities():
    packet = build_what_matters_now_packet(
        "What are my top priorities right now?",
        {"unresolved_questions": ["Finish current task"]},
        {
            "active": True,
            "pattern_threshold_met": True,
            "current_relevance": "current",
            "pattern_query": "Protect recovery structure",
            "evidence_refs": ["memory_recovery:1", "memory_health:2"],
        },
        {
            "candidates": [
                {"text": "Follow through on decision", "confidence": 0.9, "basis": "Explicit decision"},
                {"text": "Prepare next step", "confidence": 0.8, "basis": "Unfinished work"},
            ]
        },
        {
            "active": True,
            "turning_points": [{"summary": "Recent qualification", "evidence_ref": "episodic_memories:1"}],
        },
        {"active": True, "unresolved_threads": ["Call back a family member"]},
        {"active": True, "unknowns": ["Confirm current evidence"]},
        {"claim_policy": {"fact_allowed": True}},
    )
    assert len(packet["priorities"]) == 3
    assert packet["governance"]["max_priorities"] == 3


def test_weak_factual_confidence_does_not_create_a_fake_life_plan():
    packet = build_what_matters_now_packet(
        "What matters most?",
        {},
        {
            "active": True,
            "pattern_threshold_met": True,
            "current_relevance": "current",
            "pattern_query": "A possible pattern",
            "evidence_refs": ["memory_general:1"],
        },
        {},
        {},
        {},
        {},
        {"claim_policy": {"fact_allowed": False}},
    )
    assert packet["active"] is True
    assert packet["priorities"] == []
    assert packet["governance"]["missing_evidence_can_result_in_no_priority"] is True


def test_priorities_are_advisory_not_obligations():
    packet = build_what_matters_now_packet(
        "What matters now?",
        {"unresolved_questions": ["Review the next layer"]},
        {},
        {},
        {},
        {},
        {},
        {"claim_policy": {"fact_allowed": True}},
    )
    assert packet["priorities"][0]["is_obligation"] is False
    assert packet["governance"]["doug_retains_agency"] is True
    assert packet["governance"]["autonomous_actions"] is False
