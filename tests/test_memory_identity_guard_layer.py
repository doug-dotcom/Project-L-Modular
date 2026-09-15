from core.cognition.memory_identity_guard import build_memory_identity_guard_packet


def _cue():
    return {"active": True}


def _surface(source="memory_general:1"):
    return {"active": True, "decision": "surface", "surface_allowed": True, "source": source}


def _rhee(text, source="memory_general:1", extra=None):
    rows = [{"source": source, "quote_source": text, "role": "user"}]
    rows.extend(extra or [])
    return {"evidence": rows}


def test_single_episode_can_surface_only_as_event_not_identity():
    packet = build_memory_identity_guard_packet(
        "This feels similar to before.",
        _cue(),
        _surface(),
        _rhee("Last time I felt overwhelmed after the meeting and went home early."),
    )
    assert packet["decision"] == "surface"
    assert packet["surface_allowed"] is True
    assert packet["identity_claim_allowed"] is False
    assert packet["mode"] == "event_only"


def test_fixed_trait_language_without_repeated_support_is_blocked():
    packet = build_memory_identity_guard_packet(
        "This feels similar to before.",
        _cue(),
        _surface(),
        _rhee("I am the kind of person who always withdraws when things get hard."),
    )
    assert packet["decision"] == "silent"
    assert packet["surface_allowed"] is False
    assert packet["mode"] == "identity_reification_blocked"


def test_identity_question_with_repeated_direct_statements_can_allow_bounded_identity_claim():
    packet = build_memory_identity_guard_packet(
        "I am trying to understand my identity. Am I someone who values structure?",
        _cue(),
        _surface(),
        _rhee(
            "I am someone who values structure.",
            extra=[
                {"source": "memory_general:2", "quote_source": "My identity includes being someone who values structure.", "role": "user"},
            ],
        ),
    )
    assert packet["identity_claim_allowed"] is True
    assert packet["surface_allowed"] is True


def test_change_evidence_prevents_historical_identity_from_overriding_current_self():
    packet = build_memory_identity_guard_packet(
        "This feels familiar.",
        _cue(),
        _surface(),
        _rhee("I used to think I was emotionally unavailable, but that changed and I am different now."),
    )
    assert packet["surface_allowed"] is True
    assert packet["mode"] == "historical_not_current_identity"
    assert packet["governance"]["current_identity_outranks_history"] is True


def test_prior_silent_decision_cannot_be_upgraded():
    packet = build_memory_identity_guard_packet(
        "Who am I?",
        _cue(),
        {"active": True, "decision": "silent", "surface_allowed": False, "source": None},
        _rhee("I am someone who values structure."),
    )
    assert packet["decision"] == "silent"
    assert packet["surface_allowed"] is False


def test_no_associative_memory_means_not_required():
    packet = build_memory_identity_guard_packet(
        "Hello",
        {"active": False},
        {},
        {},
    )
    assert packet["active"] is False
    assert packet["decision"] == "not_required"
