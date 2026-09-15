from core.cognition.memory_value import build_memory_value_packet


def _cue():
    return {"active": True}


def _relevance(source="memory_general:1", relevance=0.9):
    return {
        "active": True,
        "decision": "surface",
        "surface": [{"source": source, "relevance": relevance}],
    }


def _contrast(source="memory_general:1"):
    return {
        "active": True,
        "decision": "surface",
        "surface_allowed": True,
        "winner": source,
    }


def _rhee(source="memory_general:1", passage=""):
    return {
        "evidence": [{
            "source": source,
            "role": "user",
            "quote_source": passage,
        }]
    }


def test_relevant_but_redundant_memory_is_not_surfaced():
    packet = build_memory_value_packet(
        "I feel calm after my dive again.",
        _cue(),
        _relevance(),
        _contrast(),
        _rhee(passage="I felt calm after my dive."),
    )
    assert packet["active"] is True
    assert packet["surface_allowed"] is False
    assert packet["decision"] in {"silent", "discard"}
    assert packet["expected_answer_delta"] in {"modest", "negligible"}


def test_prior_lesson_can_surface_when_it_changes_current_guidance():
    packet = build_memory_value_packet(
        "This keeps happening after diving. What should I do next?",
        _cue(),
        _relevance(),
        _contrast(),
        _rhee(passage=(
            "Last time this happened I learned that slowing down and resting helped, "
            "because pushing on made it worse."
        )),
    )
    assert packet["decision"] == "surface"
    assert packet["surface_allowed"] is True
    assert packet["expected_answer_delta"] == "material"
    assert packet["signals"]["memory_has_lesson"] is True


def test_value_gate_never_upgrades_silent_permission():
    packet = build_memory_value_packet(
        "What should I do? This keeps happening again.",
        _cue(),
        _relevance(),
        {
            "active": True,
            "decision": "silent",
            "surface_allowed": False,
            "winner": None,
        },
        _rhee(passage="I learned exactly what worked before."),
    )
    assert packet["surface_allowed"] is False
    assert packet["decision"] == "silent"
    assert packet["governance"]["can_upgrade_prior_permission"] is False


def test_value_gate_does_not_run_without_associative_memory():
    packet = build_memory_value_packet(
        "Hello",
        {"active": False},
        {},
        {},
        {},
    )
    assert packet["active"] is False
    assert packet["decision"] == "not_required"
