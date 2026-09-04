from types import SimpleNamespace

from agents.allegra.growth_retrieval import (
    retrieve_growth_context,
    retrieve_growth_records,
)
from agents.allegra.llgr_storage import (
    application_eligible,
    lesson_fingerprint,
    merge_llgr,
    store_llgr,
)
from agents.coach.mary_coach_adapter import build_source_reference
from agents.rhee import rhee_v3


class ReadTable:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class ReadClient:
    def __init__(self, rows):
        self.rows = rows

    def table(self, table_name):
        assert table_name == "allegra_history"
        return ReadTable(self.rows)


class ForbiddenClient:
    def table(self, _table_name):
        raise AssertionError("database must not be called")


def growth_row(lesson, sources=None, validated=0, contradictions=0, adjustment=""):
    return {
        "id": lesson,
        "stored_at": "2026-09-04T00:00:00+00:00",
        "llgr": {
            "lesson": lesson,
            "adjustment": adjustment,
            "source_references": sources or [],
            "validated_occurrences": validated,
            "contradiction_count": contradictions,
        },
    }


def test_lesson_fingerprint_ignores_case_spacing_and_punctuation():
    assert lesson_fingerprint(" Trust your judgement. ") == lesson_fingerprint(
        "trust   your JUDGEMENT"
    )


def test_legacy_occurrence_inflation_is_reset_to_traceable_sources():
    merged, is_new = merge_llgr(
        {"lesson": "Protection is a recurring value.", "occurrences": 2809},
        {"lesson": "Protection is a recurring value.", "validated": False},
        "raw_catchall:101",
    )

    assert is_new is True
    assert merged["legacy_occurrences"] == 2809
    assert merged["occurrences"] == 1
    assert merged["source_references"] == ["raw_catchall:101"]
    assert merged["application_eligible"] is False


def test_same_source_cannot_reinforce_a_pattern_twice():
    first, _ = merge_llgr(
        {},
        {"lesson": "External certainty is being sought.", "validated": True},
        "raw_catchall:1",
    )
    replay, is_new = merge_llgr(
        first,
        {"lesson": "External certainty is being sought.", "validated": True},
        "raw_catchall:1",
    )

    assert is_new is False
    assert replay["occurrences"] == 1
    assert replay["validated_occurrences"] == 1


def test_two_independent_validated_sources_activate_a_pattern():
    first, _ = merge_llgr(
        {},
        {"lesson": "External certainty is being sought.", "validated": True},
        "raw_catchall:1",
    )
    second, _ = merge_llgr(
        first,
        {"lesson": "External certainty is being sought.", "validated": True},
        "raw_catchall:2",
    )

    assert second["occurrences"] == 2
    assert second["confidence"] == 65
    assert second["pattern_status"] == "active"
    assert second["application_eligible"] is True


def test_contradictions_can_block_application():
    assert application_eligible(2, 65, contradiction_count=2) is False


def test_generic_placeholder_is_rejected_before_database_access():
    outcome = store_llgr(
        {"lesson": "A meaningful pattern has been detected and requires further exploration."},
        source_reference="raw_catchall:1",
        client=ForbiddenClient(),
    )
    assert outcome == {"stored": False, "reason": "non_specific_lesson"}


def test_retrieval_excludes_inflated_legacy_rows_and_unrelated_patterns():
    rows = [
        {
            "id": "legacy",
            "stored_at": "2026-06-12T00:00:00+00:00",
            "llgr": {"lesson": "Generic old claim", "occurrences": 2809, "confidence": 100},
        },
        growth_row(
            "External certainty is being sought during uncertainty.",
            ["raw_catchall:1", "raw_catchall:2"],
            validated=2,
            adjustment="Notice validation seeking sooner.",
        ),
        growth_row(
            "Protection is a recurring value.",
            ["raw_catchall:3", "raw_catchall:4"],
            validated=2,
        ),
    ]

    records = retrieve_growth_records(
        query="Why do I seek external validation and certainty?",
        client=ReadClient(rows),
    )

    assert [record["lesson"] for record in records] == [
        "External certainty is being sought during uncertainty."
    ]


def test_growth_context_is_clean_weighted_and_provenanced():
    rows = [
        growth_row(
            "External certainty is being sought during uncertainty.",
            ["raw_catchall:1", "raw_catchall:2"],
            validated=2,
            adjustment="Notice validation seeking sooner.",
        )
    ]
    context = retrieve_growth_context(query="external certainty", client=ReadClient(rows))

    assert len(context) == 1
    assert "confidence 65%" in context[0]
    assert "2 independent sources" in context[0]
    assert "raw_catchall:1" in context[0]
    assert "Action: Notice validation seeking sooner." in context[0]


def test_memory_adapter_uses_raw_record_as_authoritative_source():
    assert build_source_reference({"id": 55, "raw_id": 12}) == "raw_catchall:12"
    assert build_source_reference({"id": 55}) == "memory:55"
    assert build_source_reference({}) is None


def test_rhee_uses_clean_growth_retrieval_not_raw_allegra_json(monkeypatch):
    class EmptyClient:
        def table(self, _table_name):
            return ReadTable([])

    monkeypatch.setattr(rhee_v3, "supabase", EmptyClient())
    monkeypatch.setattr(
        rhee_v3,
        "retrieve_growth_context",
        lambda **_kwargs: [
            "Trust your judgement (confidence 65%, 2 independent sources)."
        ],
    )

    context = rhee_v3.load_learnings(user_message="Should I trust my judgement?")

    assert "ALLEGRA GROWTH PATTERNS" in context
    assert "Trust your judgement" in context
    assert "'llgr':" not in context
