from core.cognition.associative_saturation import AssociativeRetrievalGovernor


def test_first_background_cue_is_allowed():
    guard = AssociativeRetrievalGovernor(cooldown_seconds=45)
    result = guard.evaluate_cue(
        "room-a",
        "I feel stuck with the same recovery pattern again",
        0.9,
        now=100.0,
    )
    assert result["allowed"] is True
    assert result["reason"] == "novel_or_material_cue"


def test_repeated_near_identical_cue_inside_cooldown_is_suppressed():
    guard = AssociativeRetrievalGovernor(cooldown_seconds=45)
    guard.evaluate_cue(
        "room-a",
        "I feel stuck with the same recovery pattern again",
        0.8,
        now=100.0,
    )
    result = guard.evaluate_cue(
        "room-a",
        "I am stuck in that same recovery pattern again",
        0.8,
        now=110.0,
    )
    assert result["allowed"] is False
    assert result["reason"] == "cooldown_repeated_cue"


def test_same_thread_can_be_checked_again_after_cooldown():
    guard = AssociativeRetrievalGovernor(cooldown_seconds=45)
    guard.evaluate_cue("room-a", "My sleep feels like the same problem again", 0.8, now=100.0)
    result = guard.evaluate_cue("room-a", "My sleep feels like the same problem again tonight", 0.8, now=160.0)
    assert result["allowed"] is True


def test_strong_novel_cue_can_break_cooldown():
    guard = AssociativeRetrievalGovernor(cooldown_seconds=45)
    guard.evaluate_cue("room-a", "My recovery meeting felt familiar again", 0.9, now=100.0)
    result = guard.evaluate_cue(
        "room-a",
        "My diving ears felt exactly like a previous equalisation problem",
        0.95,
        now=110.0,
    )
    assert result["allowed"] is True
    assert result["high_value_new_cue"] is True


def test_explicit_recall_is_never_throttled():
    guard = AssociativeRetrievalGovernor(cooldown_seconds=45)
    plan = {
        "needs": {"cue_driven_memory": False},
        "signals": {"explicit_recall": True},
        "associative_cue": {"score": 0.9},
    }
    result = guard.evaluate(
        "room-a",
        "Deep recall my recovery pattern",
        plan,
        now=105.0,
    )
    assert result["allowed"] is True
    assert result["reason"] == "explicit_recall_bypass"


def test_same_turn_rechecks_are_idempotent_not_extra_probes():
    guard = AssociativeRetrievalGovernor(cooldown_seconds=45)
    first = guard.evaluate_cue("room-a", "This same family feeling is happening again", 0.9, now=100.0)
    second = guard.evaluate_cue("room-a", "This same family feeling is happening again", 0.9, now=101.0)
    assert first["allowed"] is True
    assert second["allowed"] is True
    assert second["idempotent_reuse"] is True
    assert second["recent_probe_count"] == 1
