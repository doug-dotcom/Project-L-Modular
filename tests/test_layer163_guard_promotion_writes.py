"""Layer 163 — every live promotion write revalidates durable task binding."""

from types import SimpleNamespace

import pytest

from core.cognition.durable_tasks import DurableTaskBindingError


class Query:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name
        self.pending_insert = None
        self.pending_update = None
        self.filters = {}

    def select(self, *_args):
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def limit(self, _value):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def insert(self, payload):
        self.pending_insert = dict(payload)
        return self

    def update(self, payload):
        self.pending_update = dict(payload)
        return self

    def execute(self):
        rows = self.database.rows.setdefault(self.table_name, [])
        if self.pending_insert is not None:
            stored = {"id": len(rows) + 1, **self.pending_insert}
            rows.append(stored)
            self.database.events.append(("insert", self.table_name))
            return SimpleNamespace(data=[stored])
        if self.pending_update is not None:
            updated = []
            for row in rows:
                if all(row.get(key) == value for key, value in self.filters.items()):
                    row.update(self.pending_update)
                    updated.append(dict(row))
            if updated:
                self.database.events.append(("update", self.table_name))
            return SimpleNamespace(data=updated)
        matches = [
            dict(row)
            for row in rows
            if all(row.get(key) == value for key, value in self.filters.items())
        ]
        return SimpleNamespace(data=matches)


class Database:
    def __init__(self, events):
        self.events = events
        self.rows = {}

    def table(self, table_name):
        return Query(self, table_name)


def promoted_row():
    return {
        "id": 163,
        "role": "user",
        "content": (
            "On 3 September 2026 I launched Project L. "
            "I prefer context first when I learn. "
            "I learned that evidence before confidence keeps me grounded."
        ),
        "created_at": "2026-09-03T10:00:00+00:00",
    }


def index(events, item):
    return events.index(item)


def test_live_pipeline_guards_each_actual_promotion_write(monkeypatch):
    from core.cognition import brain_pipeline

    events = []
    database = Database(events)
    monkeypatch.setattr(brain_pipeline, "supabase", database)

    def guard(stage):
        events.append(("guard", stage))

    result = brain_pipeline.process_raw_memory(promoted_row(), write_guard=guard)

    target = result["target"]
    assert result["status"] == "processed"
    assert index(events, ("guard", "promoting_long_term_memory")) < index(
        events, ("insert", target)
    )
    assert index(events, ("guard", "saving_specialised_episodic")) < index(
        events, ("insert", "episodic_memories")
    )
    assert index(events, ("guard", "saving_specialised_identity_anchor")) < index(
        events, ("insert", "identity_anchors")
    )
    assert index(events, ("guard", "saving_governed_learning")) < index(
        events, ("insert", "allegra_history")
    )


def test_specialised_binding_loss_stops_later_promotion_writes(monkeypatch):
    from core.cognition import brain_pipeline

    events = []
    database = Database(events)
    monkeypatch.setattr(brain_pipeline, "supabase", database)

    def guard(stage):
        events.append(("guard", stage))
        if stage == "saving_specialised_identity_anchor":
            raise DurableTaskBindingError("synthetic binding loss")

    with pytest.raises(DurableTaskBindingError):
        brain_pipeline.process_raw_memory(promoted_row(), write_guard=guard)

    inserted_tables = [value for kind, value in events if kind == "insert"]
    assert "episodic_memories" in inserted_tables
    assert "identity_anchors" not in inserted_tables
    assert "allegra_history" not in inserted_tables


def test_learning_binding_loss_is_not_downgraded_to_store_error(monkeypatch):
    from core.cognition import brain_pipeline

    events = []
    database = Database(events)
    monkeypatch.setattr(brain_pipeline, "supabase", database)

    def guard(stage):
        events.append(("guard", stage))
        if stage == "saving_governed_learning":
            raise DurableTaskBindingError("synthetic binding loss")

    with pytest.raises(DurableTaskBindingError):
        brain_pipeline.process_raw_memory(promoted_row(), write_guard=guard)

    assert ("guard", "saving_governed_learning") in events
    assert ("insert", "allegra_history") not in events


def test_server_pipeline_passes_bound_guard_and_propagates_binding_loss(monkeypatch):
    from api import server

    seen = {}

    def fail(_row, write_guard=None):
        seen["guard"] = write_guard
        raise DurableTaskBindingError("synthetic binding loss")

    monkeypatch.setattr(server, "process_raw_memory", fail)

    with pytest.raises(DurableTaskBindingError):
        server.run_brain_pipeline({"id": 163, "role": "user", "content": "fixture"})

    assert seen["guard"] is server.checkpoint


def test_layer163_release_marker_is_continuous():
    source = open("api/server.py", encoding="utf-8").read()
    assert source.count('"release_layer": 163') == 2
    assert source.count("release_layer=163") == 1
