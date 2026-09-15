from core.cognition.memory_applicability import build_memory_applicability_packet


def _cue():
    return {"active": True}


def _surface(source="memory_general:1"):
    return {"active": True, "decision": "surface", "surface_allowed": True, "source": source}


def _rhee(text, source="memory_general:1"):
    return {"evidence": [{"source": source, "quote_source": text, "role": "user"}]}


def test_same_domain_can_remain_surfaceable():
    packet = build_memory_applicability_packet(
        "My shoulder is sore after the gym again. What should I do?",
        _cue(),
        _surface(),
        _rhee("Last time my shoulder hurt after the gym, reducing training for two days helped."),
    )
    assert packet["decision"] == "surface"
    assert packet["surface_allowed"] is True
    assert "health" in packet["shared_domains"] or "fitness_sport" in packet["shared_domains"]


def test_cross_domain_memory_is_downgraded_without_transfer_invitation():
    packet = build_memory_applicability_packet(
        "I am unsure which investment option to choose.",
        _cue(),
        _surface(),
        _rhee("When I was stuck on a Project L deployment, slowing down and testing one change at a time helped."),
    )
    assert packet["decision"] == "silent"
    assert packet["surface_allowed"] is False
    assert packet["mode"] == "uncertain_transfer"


def test_explicit_transfer_request_allows_analogy_not_rule():
    packet = build_memory_applicability_packet(
        "Can I use that same principle from the project here with this investment decision?",
        _cue(),
        _surface(),
        _rhee("During the Project L build, testing one change at a time helped avoid confusion."),
    )
    assert packet["decision"] == "surface"
    assert packet["surface_allowed"] is True
    assert packet["mode"] in {"analogy_only", "context_aligned"}
    assert packet["governance"]["analogy_is_not_fact"] is True


def test_prior_silent_permission_cannot_be_upgraded():
    packet = build_memory_applicability_packet(
        "This feels similar to before.",
        _cue(),
        {"active": True, "decision": "silent", "surface_allowed": False, "source": None},
        _rhee("A prior situation helped."),
    )
    assert packet["decision"] == "silent"
    assert packet["surface_allowed"] is False


def test_no_associative_memory_means_not_required():
    packet = build_memory_applicability_packet(
        "Hello",
        {"active": False},
        {},
        {},
    )
    assert packet["active"] is False
    assert packet["decision"] == "not_required"
