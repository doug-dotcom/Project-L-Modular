from core.cognition.controller import plan_cognition
from core.cognition.relationship_intelligence import (
    build_relationship_packet,
    extract_relationship_subject,
    relationship_query_requested,
)


def _context(*lines):
    return "\n".join(lines)


def test_relationship_question_earns_memory_retrieval():
    plan = plan_cognition("Tell me about Steve Pampel")
    assert plan["problem_type"] == "relationship_intelligence"
    assert plan["needs"]["memory"] is True
    assert plan["needs"]["relationship_intelligence"] is True
    assert plan["signals"]["relationship_intelligence"] is True


def test_relationship_subject_is_extracted_without_profile_guessing():
    assert relationship_query_requested("Who is Steve Pampel to me?") is True
    assert extract_relationship_subject("Who is Steve Pampel to me?") == "Steve Pampel"
    assert extract_relationship_subject("How are things with Steve Pampel?") == "Steve Pampel"


def test_explicit_relationship_role_is_preserved():
    packet = build_relationship_packet(
        "Who is Steve Pampel to me?",
        _context(
            "95 | memory_relationships | ID=1 | SOURCE_ROLE=USER | CREATED_AT=2026-09-01T00:00:00+00:00",
            "2026-09-01 Steve Pampel is my best friend and lives in Canada.",
        ),
    )
    assert packet["active"] is True
    assert packet["subject"] == "Steve Pampel"
    assert packet["explicit_relationship_labels"][0]["role"] == "best friend"
    assert packet["evidence_count"] == 1


def test_old_relationship_label_is_not_automatically_current():
    packet = build_relationship_packet(
        "Tell me about Leah",
        _context(
            "91 | memory_relationships | ID=2 | SOURCE_ROLE=USER | CREATED_AT=2025-07-27T00:00:00+00:00",
            "2025-07-27 My relationship with Leah ended.",
        ),
    )
    assert packet["current_status_verified"] is False
    assert "ended" in packet["latest_status_markers"]
    assert packet["governance"]["historical_label_is_current_by_default"] is False


def test_recent_events_and_unresolved_threads_are_kept_separate():
    packet = build_relationship_packet(
        "What's been happening with Cass?",
        _context(
            "88 | memory_relationships | ID=3 | SOURCE_ROLE=USER | CREATED_AT=2026-09-10T00:00:00+00:00",
            "2026-09-10 I spoke to Cass about Shine Travel.",
            "87 | memory_relationships | ID=4 | SOURCE_ROLE=USER | CREATED_AT=2026-09-12T00:00:00+00:00",
            "2026-09-12 I still need to follow up with Cass about the latest Travel changes.",
        ),
    )
    assert len(packet["recent_events"]) == 2
    assert len(packet["unresolved_threads"]) == 1
    assert "follow up" in packet["unresolved_threads"][0]["summary"].lower()


def test_other_person_motives_are_never_authorised_as_facts():
    packet = build_relationship_packet(
        "Tell me about Steve Pampel",
        _context(
            "90 | memory_relationships | ID=5 | SOURCE_ROLE=USER | CREATED_AT=2026-09-13T00:00:00+00:00",
            "2026-09-13 I think Steve was worried about me.",
        ),
    )
    assert packet["governance"]["motives_may_be_inferred"] is False
    assert packet["governance"]["feelings_may_be_inferred"] is False
    assert packet["governance"]["doug_perspective_is_other_person_fact"] is False
