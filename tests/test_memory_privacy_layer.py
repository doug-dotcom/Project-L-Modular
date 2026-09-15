from core.cognition.memory_privacy import build_memory_privacy_packet


def _cue():
    return {"active": True}


def _surface(source="memory_general:1"):
    return {"active": True, "decision": "surface", "surface_allowed": True, "source": source}


def _rhee(text, source="memory_general:1"):
    return {"evidence": [{"source": source, "quote_source": text, "role": "user"}]}


def test_high_intimacy_memory_stays_silent_when_not_invited():
    packet = build_memory_privacy_packet(
        "I am feeling a bit flat today and not sure why.",
        _cue(),
        _surface(),
        _rhee("I previously talked about trauma and abuse from an earlier period of my life."),
    )
    assert packet["decision"] == "silent"
    assert packet["surface_allowed"] is False
    assert packet["mode"] == "protective_silence"


def test_same_private_topic_can_surface_when_directly_on_topic():
    packet = build_memory_privacy_packet(
        "This trauma topic is coming up again and I want to talk about it.",
        _cue(),
        _surface(),
        _rhee("I previously talked about trauma from an earlier period of my life."),
    )
    assert packet["decision"] == "surface"
    assert packet["surface_allowed"] is True
    assert packet["directly_on_topic"] is True


def test_direct_invitation_allows_minimum_necessary_surface():
    packet = build_memory_privacy_packet(
        "Remind me what happened with that private relationship issue.",
        _cue(),
        _surface(),
        _rhee("There was a breakup in a private relationship that I discussed before."),
    )
    assert packet["decision"] == "surface"
    assert packet["surface_allowed"] is True
    assert packet["direct_invitation"] is True
    assert packet["governance"]["minimum_necessary_disclosure"] is True


def test_non_intimate_memory_can_remain_surfaceable():
    packet = build_memory_privacy_packet(
        "This project problem feels familiar.",
        _cue(),
        _surface(),
        _rhee("During a previous app deployment, testing one change at a time helped."),
    )
    assert packet["decision"] == "surface"
    assert packet["surface_allowed"] is True
    assert packet["memory_categories"] == []


def test_prior_silent_permission_cannot_be_upgraded():
    packet = build_memory_privacy_packet(
        "Tell me about that trauma topic.",
        _cue(),
        {"active": True, "decision": "silent", "surface_allowed": False, "source": None},
        _rhee("A trauma memory."),
    )
    assert packet["decision"] == "silent"
    assert packet["surface_allowed"] is False


def test_no_associative_memory_means_not_required():
    packet = build_memory_privacy_packet(
        "Hello",
        {"active": False},
        {},
        {},
    )
    assert packet["active"] is False
    assert packet["decision"] == "not_required"
