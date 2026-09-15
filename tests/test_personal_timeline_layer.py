from datetime import date

from core.cognition.controller import plan_cognition
from core.cognition.personal_timeline import (
    build_personal_timeline_packet,
    timeline_query_requested,
)


def _evidence(*lines):
    return "\n".join(lines)


def test_turning_point_language_forces_memory_and_longitudinal_reasoning():
    plan = plan_cognition("What were the biggest turning points this year?")
    assert plan["problem_type"] == "personal_timeline"
    assert plan["needs"]["memory"] is True
    assert plan["needs"]["longitudinal_reasoning"] is True
    assert plan["needs"]["personal_timeline"] is True


def test_story_of_year_is_timeline_request():
    assert timeline_query_requested("Tell me the story of 2026 so far") is True


def test_timeline_sorts_dated_evidence_chronologically():
    context = _evidence(
        "90 | memory_recovery | ID=2 | SOURCE_ROLE=USER | CREATED_AT=2026-06-11T00:00:00+00:00",
        "2026-06-11 Reached six months sober milestone.",
        "95 | memory_project_l | ID=1 | SOURCE_ROLE=USER | CREATED_AT=2026-09-02T00:00:00+00:00",
        "2026-09-02 Project L launched.",
    )
    packet = build_personal_timeline_packet(
        "Give me my 2026 timeline",
        context,
        today=date(2026, 9, 15),
    )
    assert packet["active"] is True
    assert [item["event_date"] for item in packet["events"]] == ["2026-06-11", "2026-09-02"]
    assert packet["window"]["mode"] == "year"


def test_month_query_filters_to_requested_month():
    context = _evidence(
        "90 | memory_health | ID=1 | SOURCE_ROLE=USER | CREATED_AT=2026-07-04T00:00:00+00:00",
        "2026-07-04 Health routine changed.",
        "92 | memory_project_l | ID=2 | SOURCE_ROLE=USER | CREATED_AT=2026-08-01T00:00:00+00:00",
        "2026-08-01 Started a new Project L phase.",
    )
    packet = build_personal_timeline_packet(
        "What changed around July?",
        context,
        today=date(2026, 9, 15),
    )
    assert packet["window"]["mode"] == "month"
    assert len(packet["events"]) == 1
    assert packet["events"][0]["event_date"] == "2026-07-04"


def test_undated_evidence_is_not_given_an_invented_date():
    context = _evidence(
        "99 | memory_general | ID=1 | SOURCE_ROLE=USER",
        "This was an important breakthrough but no date was recorded.",
    )
    packet = build_personal_timeline_packet(
        "Show me my timeline",
        context,
        today=date(2026, 9, 15),
    )
    assert packet["events"] == []
    assert packet["status"] == "no_dated_evidence"
    assert packet["governance"]["invent_dates"] is False


def test_turning_points_require_change_or_milestone_language():
    context = _evidence(
        "90 | memory_general | ID=1 | SOURCE_ROLE=USER | CREATED_AT=2026-05-01T00:00:00+00:00",
        "2026-05-01 Had lunch at home.",
        "91 | memory_recovery | ID=2 | SOURCE_ROLE=USER | CREATED_AT=2026-06-11T00:00:00+00:00",
        "2026-06-11 Reached a major recovery milestone.",
    )
    packet = build_personal_timeline_packet(
        "What were my turning points?",
        context,
        today=date(2026, 9, 15),
    )
    assert len(packet["events"]) == 2
    assert len(packet["turning_points"]) == 1
    assert packet["turning_points"][0]["event_date"] == "2026-06-11"
