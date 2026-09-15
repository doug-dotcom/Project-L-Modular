from datetime import datetime, timezone

from core.cognition.controller import plan_cognition
from core.cognition.longitudinal import build_longitudinal_packet, life_pattern_requested


def _evidence(*blocks):
    return "\n".join(blocks)


def test_natural_pattern_language_earns_memory_and_longitudinal_reasoning():
    plan = plan_cognition("L what have you noticed about me lately across my life?")
    assert plan["problem_type"] == "life_pattern"
    assert plan["needs"]["memory"] is True
    assert plan["needs"]["longitudinal_reasoning"] is True
    assert plan["needs"]["structured_reasoning"] is True
    assert plan["needs"]["life_pattern"] is True


def test_join_the_dots_is_a_life_pattern_request():
    assert life_pattern_requested("Can you join the dots for me?") is True
    plan = plan_cognition("Can you join the dots for me?")
    assert plan["signals"]["life_pattern"] is True


def test_cross_domain_pattern_requires_two_supporting_domains():
    context = _evidence(
        "90 | memory_health | ID=1 | SOURCE_ROLE=USER | CREATED_AT=2026-09-01T00:00:00+00:00",
        "2026-09-01 Better sleep followed a calmer week.",
        "88 | memory_health | ID=2 | SOURCE_ROLE=USER | CREATED_AT=2026-09-08T00:00:00+00:00",
        "2026-09-08 Exercise felt easier after good sleep.",
    )
    packet = build_longitudinal_packet(
        "What recurring themes do you notice across my life?",
        context,
        now=datetime(2026, 9, 15, tzinfo=timezone.utc),
    )
    assert packet["pattern_scope"] == "cross_domain_life"
    assert packet["supporting_domains"] == ["health"]
    assert packet["cross_domain_threshold_met"] is False
    assert packet["pattern_threshold_met"] is False


def test_cross_domain_pattern_can_clear_threshold_with_independent_domains():
    context = _evidence(
        "92 | memory_health | ID=1 | SOURCE_ROLE=USER | CREATED_AT=2026-09-01T00:00:00+00:00",
        "2026-09-01 Better sleep followed a calmer week.",
        "91 | memory_recovery | ID=2 | SOURCE_ROLE=USER | CREATED_AT=2026-09-08T00:00:00+00:00",
        "2026-09-08 Recovery felt steadier when routine was simple.",
    )
    packet = build_longitudinal_packet(
        "L what have you noticed across my life?",
        context,
        now=datetime(2026, 9, 15, tzinfo=timezone.utc),
    )
    assert packet["supporting_domains"] == ["health", "recovery"]
    assert packet["cross_domain_support"] == 2
    assert packet["cross_domain_threshold_met"] is True
    assert packet["pattern_threshold_met"] is True


def test_contradictions_are_preserved_not_hidden():
    context = _evidence(
        "92 | memory_health | ID=1 | SOURCE_ROLE=USER | CREATED_AT=2026-09-01T00:00:00+00:00",
        "2026-09-01 Routine helped my sleep.",
        "91 | memory_recovery | ID=2 | SOURCE_ROLE=USER | CREATED_AT=2026-09-08T00:00:00+00:00",
        "2026-09-08 Recovery routine helped me feel grounded.",
        "89 | memory_health | ID=3 | SOURCE_ROLE=USER | CREATED_AT=2026-09-12T00:00:00+00:00",
        "2026-09-12 That no longer happens; routine did not help this week.",
    )
    packet = build_longitudinal_packet(
        "What recurring themes do you notice across my life?",
        context,
        now=datetime(2026, 9, 15, tzinfo=timezone.utc),
    )
    assert len(packet["contradicting_episodes"]) == 1
    assert packet["contradicting_episodes"][0]["domain"] == "health"
