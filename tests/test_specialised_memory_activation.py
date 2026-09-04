from pathlib import Path

from memory.promotion.specialised import (
    build_episodic_payload,
    build_identity_anchor_payload,
    extract_event_date,
    write_specialised_memories,
)
from memory.retrieval.provenance import annotate_memory_provenance


def raw(content, raw_id=101, created_at="2026-09-03T15:30:00+00:00"):
    return {
        "id": raw_id,
        "role": "user",
        "content": content,
        "created_at": created_at,
    }


def test_exact_and_brisbane_relative_event_dates_are_normalised():
    assert extract_event_date("Luella got her braces off on 16 June 2026.")[0] == "2026-06-16"
    assert extract_event_date("RC launched on September 3, 2026.")[0] == "2026-09-03"
    assert extract_event_date("The trip started 7/09/2026.")[0] == "2026-09-07"
    # 15:30 UTC is already the next calendar day in Brisbane.
    assert extract_event_date("Today I completed my first dive.", "2026-09-03T15:30:00+00:00")[0] == "2026-09-04"


def test_milestones_create_episodes_but_chatter_and_questions_do_not():
    episode = build_episodic_payload(
        raw(
            "Please mark today as the day Luella got her braces off",
            raw_id=3269,
            created_at="2026-06-16T04:03:54+00:00",
        ),
        category="family",
    )
    assert episode["event_date"] == "2026-06-16"
    assert episode["category"] == "family"
    assert episode["source_reference"] == 3269
    assert episode["metadata"]["source_role"] == "user"

    assert build_episodic_payload(raw("Today I feel okay")) is None
    assert build_episodic_payload(raw("When did Luella get her braces off?")) is None
    assert build_episodic_payload({**raw("Today I completed my first dive"), "role": "assistant"}) is None


def test_stable_first_person_truths_create_anchors_not_temporary_states():
    anchor = build_identity_anchor_payload(
        raw("My preferred learning style starts with context and then terminology.", raw_id=88)
    )
    assert anchor == {
        "key": "learning_style:raw_88",
        "value": "My preferred learning style starts with context and then terminology.",
        "confidence": 0.95,
        "source_reference": 88,
        "memory_status": "ACTIVE",
    }

    assert build_identity_anchor_payload(raw("I am tired today")) is None
    assert build_identity_anchor_payload(raw("I am excited about Bali")) is None
    assert build_identity_anchor_payload(raw("L what are my values")) is None
    assert build_identity_anchor_payload(raw("Feedback for L: I am L and my purpose is continuity.")) is None
    assert build_identity_anchor_payload(raw("I believe this" + " is a report" * 100)) is None


class Query:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.payload = None
        self.source_reference = None

    def select(self, *args):
        return self

    def eq(self, column, value):
        assert column == "source_reference"
        self.source_reference = value
        return self

    def limit(self, value):
        return self

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        if self.payload is not None:
            self.client.rows[self.table_name].append(dict(self.payload))
            return type("Response", (), {"data": [self.payload]})()
        matches = [
            row for row in self.client.rows[self.table_name]
            if row.get("source_reference") == self.source_reference
        ]
        return type("Response", (), {"data": matches})()


class Client:
    def __init__(self):
        self.rows = {"episodic_memories": [], "identity_anchors": []}

    def table(self, table_name):
        return Query(self, table_name)


def test_specialised_writes_are_idempotent():
    client = Client()
    source = raw("On 3 September 2026 I launched RC, and I prefer recovery support with continuity.", raw_id=77)

    first = write_specialised_memories(client, source, category="project_l")
    second = write_specialised_memories(client, source, category="project_l")

    assert first == {"episodic": "stored", "identity_anchor": "stored"}
    assert second == {"episodic": "already_exists", "identity_anchor": "already_exists"}
    assert len(client.rows["episodic_memories"]) == 1
    assert len(client.rows["identity_anchors"]) == 1


def test_specialised_source_reference_restores_user_provenance():
    memory = {"source_reference": 44, "summary": "A verified milestone"}
    annotate_memory_provenance(memory, {"44": "user"})
    assert memory["_source_role"] == "user"
    assert memory["_provenance_evidence"] == "raw_catchall"


def test_both_live_long_term_promoters_call_the_specialised_writer():
    root = Path(__file__).resolve().parents[1]
    for relative_path in ("core/cognition/brain_pipeline.py", "agents/carol/carol.py"):
        source = (root / relative_path).read_text(encoding="utf-8")
        assert "write_specialised_memories(" in source
