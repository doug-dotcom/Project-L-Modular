from core.cognition.memory_emotional_salience import build_memory_emotional_salience_packet


def _cue():
    return {"active": True}


def _surface(source="memory_general:1"):
    return {"active": True, "decision": "surface", "surface_allowed": True, "source": source}


def _rhee(rows):
    return {"evidence": rows}


def test_emotional_memory_is_downweighted_when_quieter_match_exists():
    packet = build_memory_emotional_salience_packet(
        "This keeps happening with my project and I want to know what helped before.",
        _cue(),
        _surface(),
        _rhee([
            {"source": "memory_general:1", "quote_source": "I was devastated and overwhelmed when the project failed, but slowing down helped.", "role": "user"},
            {"source": "memory_general:2", "quote_source": "When the project failed, testing one change at a time helped me find the problem.", "role": "user"},
        ]),
    )
    assert packet["decision"] == "silent"
    assert packet["surface_allowed"] is False
    assert packet["mode"] == "salience_downweighted"
    assert packet["quieter_competitor"] == "memory_general:2"


def test_explicit_emotional_question_allows_emotional_memory():
    packet = build_memory_emotional_salience_packet(
        "Remind me how I felt emotionally when that project failed.",
        _cue(),
        _surface(),
        _rhee([
            {"source": "memory_general:1", "quote_source": "I was devastated and overwhelmed when the project failed.", "role": "user"},
            {"source": "memory_general:2", "quote_source": "The project failed after deployment.", "role": "user"},
        ]),
    )
    assert packet["decision"] == "surface"
    assert packet["surface_allowed"] is True
    assert packet["emotion_invited"] is True


def test_quiet_memory_is_not_penalised():
    packet = build_memory_emotional_salience_packet(
        "This keeps happening with my project. What worked before?",
        _cue(),
        _surface(),
        _rhee([
            {"source": "memory_general:1", "quote_source": "Testing one change at a time helped when the project failed.", "role": "user"},
        ]),
    )
    assert packet["decision"] == "surface"
    assert packet["surface_allowed"] is True


def test_prior_silent_cannot_be_upgraded():
    packet = build_memory_emotional_salience_packet(
        "This feels similar to before.",
        _cue(),
        {"active": True, "decision": "silent", "surface_allowed": False, "source": None},
        _rhee([]),
    )
    assert packet["decision"] == "silent"
    assert packet["surface_allowed"] is False


def test_no_associative_memory_means_not_required():
    packet = build_memory_emotional_salience_packet(
        "Hello",
        {"active": False},
        {},
        {},
    )
    assert packet["active"] is False
    assert packet["decision"] == "not_required"
