from core.cognition.controller import plan_cognition
from core.cognition.cue_driven_memory import assess_present_cue, build_cue_memory_packet
from core.cognition.evidence_evaluation import evidence_mode


def test_present_moment_can_trigger_memory_without_recall_command():
    message = "This feels like before when I got overwhelmed around my recovery routine."
    cue = assess_present_cue(message)
    assert cue["should_retrieve"] is True
    plan = plan_cognition(message)
    assert plan["needs"]["memory"] is True
    assert plan["needs"]["cue_driven_memory"] is True
    assert plan["signals"]["explicit_recall"] is False
    assert plan["problem_type"] == "conversation"


def test_generic_small_talk_does_not_probe_memory():
    assert assess_present_cue("Hello there")["should_retrieve"] is False
    plan = plan_cognition("Tell me a joke about penguins")
    assert plan["needs"]["cue_driven_memory"] is False


def test_personal_experience_without_enough_associative_signal_stays_quiet():
    cue = assess_present_cue("I feel excited about lunch today")
    assert cue["should_retrieve"] is False


def test_associative_retrieval_does_not_force_visible_citation_mode():
    message = "This feels like before when I got overwhelmed around my recovery routine."
    plan = plan_cognition(message)
    assert plan["needs"]["memory"] is True
    assert evidence_mode(message, plan["needs"]["memory"]) is False


def test_explicit_deep_recall_keeps_strict_evidence_mode():
    message = "Deep recall my recovery and show me the supporting evidence"
    plan = plan_cognition(message)
    assert plan["needs"]["memory"] is True
    assert evidence_mode(message, plan["needs"]["memory"]) is True


def test_retrieval_can_inform_silently_without_surface_permission():
    plan = {
        "needs": {"cue_driven_memory": True},
        "associative_cue": {"should_retrieve": True, "score": 0.68, "reasons": ["first_person_experience"]},
    }
    packet = build_cue_memory_packet(
        "This feels familiar.",
        plan,
        {
            "recall_active": True,
            "evidence": [{"source": "memory_recovery:1", "quote_source": "A prior recovery note."}],
        },
        {
            "claim_permissions": {
                "personal_fact": True,
                "supported_inference": True,
            }
        },
    )
    assert packet["silent_use_allowed"] is True
    assert packet["surface_candidate"] is False
    assert packet["governance"]["retrieval_equals_surface_permission"] is False


def test_strong_relevant_cue_can_become_surface_candidate_but_not_authority():
    plan = {
        "needs": {"cue_driven_memory": True},
        "associative_cue": {"should_retrieve": True, "score": 0.9, "reasons": ["recurrence_or_association"]},
    }
    packet = build_cue_memory_packet(
        "This feels like before.",
        plan,
        {
            "recall_active": True,
            "evidence": [{"source": "memory_general:9", "quote_source": "Relevant prior evidence."}],
        },
        {"claim_permissions": {"personal_fact": True, "supported_inference": False}},
    )
    assert packet["surface_candidate"] is True
    assert packet["governance"]["surface_only_if_materially_useful"] is True
    assert packet["governance"]["privacy_required"] is True
