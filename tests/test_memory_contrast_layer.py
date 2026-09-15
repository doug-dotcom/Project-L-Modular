from core.cognition.memory_contrast import build_memory_contrast_packet


def _cue():
    return {"active": True}


def _relevance(reviewed, decision="surface"):
    return {
        "active": True,
        "decision": decision,
        "reviewed": reviewed,
        "surface": [item for item in reviewed if item.get("disposition") == "surface"],
    }


def _rhee(*rows):
    return {"evidence": list(rows)}


def test_close_competing_people_blocks_surface():
    relevance = _relevance([
        {"source": "memory_relationships:1", "relevance": 0.84, "disposition": "surface"},
        {"source": "memory_relationships:2", "relevance": 0.79, "disposition": "silent"},
    ])
    packet = build_memory_contrast_packet(
        "I felt worried after talking with someone again",
        _cue(),
        relevance,
        _rhee(
            {"source": "memory_relationships:1", "quote_source": "I felt worried after talking with Steve about the trip."},
            {"source": "memory_relationships:2", "quote_source": "I felt worried after talking with Cass about the project."},
        ),
    )
    assert packet["ambiguous"] is True
    assert packet["surface_allowed"] is False
    assert packet["decision"] == "silent"


def test_explicit_person_cue_can_resolve_close_race():
    relevance = _relevance([
        {"source": "memory_relationships:1", "relevance": 0.84, "disposition": "surface"},
        {"source": "memory_relationships:2", "relevance": 0.80, "disposition": "silent"},
    ])
    packet = build_memory_contrast_packet(
        "Talking with Steve has me feeling worried again",
        _cue(),
        relevance,
        _rhee(
            {"source": "memory_relationships:1", "quote_source": "I felt worried after talking with Steve about the trip."},
            {"source": "memory_relationships:2", "quote_source": "I felt worried after talking with Cass about the project."},
        ),
    )
    assert packet["ambiguous"] is False
    assert packet["surface_allowed"] is True
    assert packet["winner"] == "memory_relationships:1"


def test_different_dates_in_close_memories_block_event_merging():
    relevance = _relevance([
        {"source": "episodic_memories:1", "relevance": 0.82, "disposition": "surface"},
        {"source": "episodic_memories:2", "relevance": 0.77, "disposition": "silent"},
    ])
    packet = build_memory_contrast_packet(
        "That dive feeling has come up again",
        _cue(),
        relevance,
        _rhee(
            {"source": "episodic_memories:1", "quote_source": "2026-09-10 I completed a deep dive and felt calm."},
            {"source": "episodic_memories:2", "quote_source": "2026-09-14 I completed another dive and felt calm."},
        ),
    )
    assert packet["ambiguous"] is True
    assert packet["governance"]["event_merging_prohibited"] is True


def test_prior_relevance_silent_cannot_be_upgraded_to_surface():
    relevance = _relevance([
        {"source": "memory_general:1", "relevance": 0.70, "disposition": "silent"},
    ], decision="silent")
    packet = build_memory_contrast_packet(
        "This feels familiar again",
        _cue(),
        relevance,
        _rhee({"source": "memory_general:1", "quote_source": "This felt familiar during an earlier week."}),
    )
    assert packet["surface_allowed"] is False
    assert packet["decision"] == "silent"


def test_no_cue_means_not_required():
    packet = build_memory_contrast_packet("Hello", {"active": False}, {}, {})
    assert packet["active"] is False
    assert packet["decision"] == "not_required"
