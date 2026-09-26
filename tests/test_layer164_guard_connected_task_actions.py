"""Layer 164 — connected write actions revalidate durable task binding."""

from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from core.cognition.durable_tasks import DurableTaskBindingError
from services import google_workspace_service as google
from services.capability_router_service import route_capability


class Executable:
    def __init__(self, value, events=None, event=None):
        self.value = value
        self.events = events
        self.event = event

    def execute(self):
        if self.events is not None and self.event is not None:
            self.events.append(self.event)
        return self.value


class TaskLists:
    def list(self, **_kwargs):
        return Executable({"items": [{"id": "list-164"}]})


class Tasks:
    def __init__(self, events):
        self.events = events

    def insert(self, **kwargs):
        return Executable(
            {"title": kwargs["body"]["title"]},
            self.events,
            ("insert", kwargs["body"]["title"]),
        )

    def list(self, **_kwargs):
        return Executable({"items": []})


class GoogleService:
    def __init__(self, events):
        self.events = events

    def tasklists(self):
        return TaskLists()

    def tasks(self):
        return Tasks(self.events)


def test_google_tasks_revalidates_binding_immediately_before_insert(monkeypatch):
    events = []
    monkeypatch.setattr(
        google,
        "_google_service",
        lambda *_args: GoogleService(events),
    )

    def guard(stage):
        events.append(("guard", stage))

    reply = google.tasks_result(
        "add to my tasks: call the electrician",
        write_guard=guard,
    )

    assert reply == "Tasks service created: call the electrician."
    assert events == [
        ("guard", "google_tasks_create"),
        ("insert", "call the electrician"),
    ]


def test_google_tasks_binding_loss_prevents_external_side_effect(monkeypatch):
    events = []
    monkeypatch.setattr(
        google,
        "_google_service",
        lambda *_args: GoogleService(events),
    )

    def guard(stage):
        events.append(("guard", stage))
        raise DurableTaskBindingError("synthetic lease loss")

    with pytest.raises(DurableTaskBindingError):
        google.tasks_result(
            "add to my tasks: must never be created",
            write_guard=guard,
        )

    assert events == [("guard", "google_tasks_create")]


def test_capability_router_propagates_binding_loss_instead_of_service_error(monkeypatch):
    events = []
    monkeypatch.setattr(
        google,
        "_google_service",
        lambda *_args: GoogleService(events),
    )

    def guard(_stage):
        raise DurableTaskBindingError("synthetic lease loss")

    with pytest.raises(DurableTaskBindingError):
        route_capability(
            "add to my tasks: never create this",
            write_guard=guard,
        )

    assert not any(kind == "insert" for kind, *_ in events)


def test_read_only_tasks_listing_does_not_require_write_guard(monkeypatch):
    events = []
    monkeypatch.setattr(
        google,
        "_google_service",
        lambda *_args: GoogleService(events),
    )

    def fail_if_called(_stage):
        raise AssertionError("read-only task listing must not invoke a write guard")

    reply = google.tasks_result(
        "show my tasks",
        write_guard=fail_if_called,
    )

    assert reply == "Tasks service returned no incomplete tasks."
    assert events == []


def test_server_passes_bound_guard_to_capability_router_and_propagates_binding_loss():
    source = Path("api/server.py").read_text(encoding="utf-8")

    call = "route_capability(user_message, write_guard=checkpoint)"
    assert call in source
    call_index = source.index(call)
    except_index = source.index("except DurableTaskBindingError:", call_index)
    generic_index = source.index("except Exception as e:", except_index)
    assert call_index < except_index < generic_index


def test_layer164_release_marker_is_continuous():
    source = Path("api/server.py").read_text(encoding="utf-8")
    layers = [
        int(value)
        for value in re.findall(r'release_layer"?\s*[:=]\s*(\d+)', source)
    ]
    assert len(layers) == 3
    assert len(set(layers)) == 1
    assert layers[0] >= 164
