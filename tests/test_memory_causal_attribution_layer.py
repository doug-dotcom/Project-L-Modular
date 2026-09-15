from core.cognition.memory_causal_attribution import build_memory_causal_attribution_packet


def _cue():
    return {"active": True}


def _surface(source="memory_general:1"):
    return {"active": True, "decision": "surface", "surface_allowed": True, "source": source}


def _rhee(text, source="memory_general:1", role="user"):
    return {"evidence": [{"source": source, "quote_source": text, "role": role}]}


def test_sequence_alone_does_not_establish_cause():
    packet = build_memory_causal_attribution_packet(
        "Why did I get anxious after that meeting?",
        _cue(),
        _surface(),
        _rhee("I felt anxious after the meeting and went home early."),
    )
    assert packet["decision"] == "silent"
    assert packet["surface_allowed"] is False
    assert packet["sequence_language"] is True
    assert packet["direct_user_attribution"] is False


def test_direct_user_causal_attribution_can_remain_surfaceable():
    packet = build_memory_causal_attribution_packet(
        "Why did I leave early that day?",
        _cue(),
        _surface(),
        _rhee("I left early because the noise was overwhelming me."),
    )
    assert packet["decision"] == "surface"
    assert packet["surface_allowed"] is True
    assert packet["direct_user_attribution"] is True
    assert packet["mode"] == "direct_cause_supported"


def test_assistant_causal_statement_does_not_become_personal_cause():
    packet = build_memory_causal_attribution_packet(
        "Why did that happen?",
        _cue(),
        _surface(),
        _rhee("That happened because you were stressed.", role="assistant"),
    )
    assert packet["decision"] == "silent"
    assert packet["surface_allowed"] is False
    assert packet["direct_user_attribution"] is False


def test_noncausal_use_is_not_unnecessarily_blocked():
    packet = build_memory_causal_attribution_packet(
        "This reminds me of that dive and what helped next.",
        _cue(),
        _surface(),
        _rhee("After the dive I rested, drank water and felt better later."),
    )
    assert packet["decision"] == "surface"
    assert packet["surface_allowed"] is True
    assert packet["mode"] == "noncausal_context"


def test_prior_silent_permission_cannot_be_upgraded():
    packet = build_memory_causal_attribution_packet(
        "Why did this happen?",
        _cue(),
        {"active": True, "decision": "silent", "surface_allowed": False, "source": None},
        _rhee("I said it happened because I was tired."),
    )
    assert packet["decision"] == "silent"
    assert packet["surface_allowed"] is False


def test_no_associative_memory_means_not_required():
    packet = build_memory_causal_attribution_packet("Hello", {"active": False}, {}, {})
    assert packet["active"] is False
    assert packet["decision"] == "not_required"
