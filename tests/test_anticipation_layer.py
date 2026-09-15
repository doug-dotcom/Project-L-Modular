from core.cognition.anticipation import build_anticipation_packet


def test_unfinished_thread_is_high_confidence_and_surfaceable():
    packet = build_anticipation_packet(
        "Go",
        {
            "unresolved_questions": ["Finish wiring the next Project L layer"],
            "recent_decisions": [],
            "conversation_phase": "execution",
        },
        {},
        {"recall_active": True},
    )
    assert packet["active"] is True
    assert packet["surfaceable_count"] >= 1
    assert packet["candidates"][0]["kind"] == "unfinished_thread"
    assert packet["candidates"][0]["confidence"] >= 0.75


def test_recent_decision_can_prepare_follow_through_without_action_authority():
    packet = build_anticipation_packet(
        "That works",
        {
            "unresolved_questions": [],
            "recent_decisions": ["We decided to deploy the continuity layer"],
            "conversation_phase": "review",
        },
        {},
        {},
    )
    candidate = packet["candidates"][0]
    assert candidate["kind"] == "decision_follow_through"
    assert candidate["action_authority"] is False
    assert packet["governance"]["autonomous_actions"] is False


def test_cross_domain_pattern_can_be_prepared_but_not_declared_fact():
    packet = build_anticipation_packet(
        "How am I going?",
        {},
        {
            "active": True,
            "pattern_threshold_met": True,
            "current_relevance": "current",
            "pattern_query": "recovery structure and health",
            "supporting_episodes": [{"id": "1"}, {"id": "2"}],
            "cross_domain_support": {"domain_count": 2, "domains": ["health", "recovery"]},
        },
        {},
    )
    assert packet["active"] is True
    assert any(item["kind"] == "current_pattern_watch" for item in packet["candidates"])
    assert packet["governance"]["prediction_is_fact"] is False


def test_no_grounded_context_means_silence_is_valid():
    packet = build_anticipation_packet("Hello", {}, {}, {})
    assert packet["active"] is False
    assert packet["candidates"] == []
    assert packet["surfaceable_count"] == 0
    assert packet["governance"]["silence_is_valid"] is True


def test_low_confidence_context_ready_is_not_surfaceable():
    packet = build_anticipation_packet(
        "Continue",
        {"current_goal": "Project L", "unresolved_questions": [], "recent_decisions": []},
        {},
        {"recall_active": True},
    )
    assert packet["active"] is True
    assert packet["candidates"][0]["kind"] == "context_ready"
    assert packet["surfaceable_count"] == 0
