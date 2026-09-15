from core.cognition.memory_counterexample import build_memory_counterexample_packet


def cue():
    return {"active": True}


def value(source="memory_general:1"):
    return {"active": True, "decision": "surface", "surface_allowed": True, "source": source}


def test_counterexample_downgrades_single_memory_story():
    rhee = {
        "evidence": [
            {"source": "memory_general:1", "quote_source": "Slowing down after diving helped and I felt better."},
            {"source": "memory_general:2", "quote_source": "After another dive I slowed down but it did not help and I felt worse."},
        ]
    }
    packet = build_memory_counterexample_packet(
        "This keeps happening after diving. What should I do next?",
        cue(),
        value(),
        rhee,
    )
    assert packet["active"] is True
    assert packet["material_counterexample_found"] is True
    assert packet["decision"] == "silent"
    assert packet["surface_allowed"] is False
    assert packet["counterexamples"]


def test_no_material_counterexample_preserves_surface_permission():
    rhee = {
        "evidence": [
            {"source": "memory_general:1", "quote_source": "Slowing down after diving helped and I felt better."},
            {"source": "memory_general:2", "quote_source": "I had lunch with Steve and it was a good afternoon."},
        ]
    }
    packet = build_memory_counterexample_packet(
        "This keeps happening after diving. What should I do next?",
        cue(),
        value(),
        rhee,
    )
    assert packet["material_counterexample_found"] is False
    assert packet["decision"] == "surface"
    assert packet["surface_allowed"] is True


def test_layer_cannot_upgrade_earlier_silent_decision():
    packet = build_memory_counterexample_packet(
        "This feels familiar again.",
        cue(),
        {"active": True, "decision": "silent", "surface_allowed": False},
        {"evidence": []},
    )
    assert packet["decision"] == "silent"
    assert packet["surface_allowed"] is False


def test_no_associative_memory_means_not_required():
    packet = build_memory_counterexample_packet(
        "Hello there",
        {"active": False},
        {"active": False},
        {"evidence": []},
    )
    assert packet["active"] is False
    assert packet["decision"] == "not_required"
