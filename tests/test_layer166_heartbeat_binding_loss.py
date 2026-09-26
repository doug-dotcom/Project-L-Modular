"""Layer 166 — definitive heartbeat binding loss propagates cooperatively."""

import threading
from uuid import uuid4

from core.cognition.durable_tasks import (
    CONTEXT,
    DurableTaskBindingError,
    TaskRunner,
    checkpoint,
    request_hash,
)


def bound_task(message="layer 166"):
    request_id = str(uuid4())
    request = {"request_id": request_id, "message": message}
    return {
        "request_id": request_id,
        "request": request,
        "input_hash": request_hash(request),
        "_request_integrity": {
            "version": "1.0",
            "status": "verified",
            "valid": True,
            "issues": [],
            "request_id_bound": True,
        },
    }


class BaseStore:
    def __init__(self):
        self.progressed = []
        self.finished = []

    def finish_bound(
        self, request_id, worker, input_hash, request, payload, status="ready"
    ):
        self.finished.append((status, payload))
        return True


class RejectingHeartbeatStore(BaseStore):
    def progress_bound(
        self, request_id, worker, input_hash, request, stage=None
    ):
        self.progressed.append(stage)
        return stage is not None


class UncertainHeartbeatStore(BaseStore):
    def __init__(self):
        super().__init__()
        self.heartbeat_attempted = threading.Event()
        self.heartbeat_calls = 0

    def progress_bound(
        self, request_id, worker, input_hash, request, stage=None
    ):
        self.progressed.append(stage)
        if stage is None:
            self.heartbeat_calls += 1
            self.heartbeat_attempted.set()
            if self.heartbeat_calls == 1:
                raise ConnectionError("synthetic transport uncertainty")
        return True


def test_definitive_heartbeat_rejection_stops_next_guard_without_second_rpc():
    store = RejectingHeartbeatStore()
    effects = []

    def execute(_request):
        binding_lost = CONTEXT.task[5]
        assert binding_lost.wait(0.5)
        checkpoint("connected_actions")
        effects.append("must-not-run")
        return {"reply": "must not complete"}

    TaskRunner(
        store,
        execute,
        heartbeat_seconds=0.001,
    ).run_one(bound_task(), str(uuid4()))

    assert effects == []
    assert store.progressed.count(None) == 1
    assert "connected_actions" not in store.progressed
    assert store.finished
    assert store.finished[-1][0] == "failed"


def test_definitive_heartbeat_loss_prevents_success_finish_after_long_work():
    store = RejectingHeartbeatStore()

    def execute(_request):
        binding_lost = CONTEXT.task[5]
        assert binding_lost.wait(0.5)
        return {"reply": "work returned after ownership loss"}

    TaskRunner(
        store,
        execute,
        heartbeat_seconds=0.001,
    ).run_one(bound_task(), str(uuid4()))

    assert store.finished
    assert [status for status, _payload in store.finished] == ["failed"]


def test_heartbeat_transport_error_does_not_claim_binding_was_lost():
    store = UncertainHeartbeatStore()
    effects = []

    def execute(_request):
        assert store.heartbeat_attempted.wait(0.5)
        checkpoint("connected_actions")
        effects.append("action")
        return {"reply": "done"}

    TaskRunner(
        store,
        execute,
        heartbeat_seconds=0.001,
    ).run_one(bound_task(), str(uuid4()))

    assert effects == ["action"]
    assert "connected_actions" in store.progressed
    assert store.finished[-1][0] == "ready"


def test_checkpoint_that_discovers_loss_sets_shared_signal():
    class Store(BaseStore):
        def progress_bound(
            self, request_id, worker, input_hash, request, stage=None
        ):
            self.progressed.append(stage)
            return False

    store = Store()
    task = bound_task()
    lost = threading.Event()
    CONTEXT.task = (
        store,
        task["request_id"],
        str(uuid4()),
        task["input_hash"],
        task["request"],
        lost,
    )
    try:
        try:
            checkpoint("saving_raw_answer")
        except DurableTaskBindingError:
            pass
        else:
            raise AssertionError("binding loss must stop the checkpoint")
    finally:
        CONTEXT.task = None

    assert lost.is_set() is True
    assert store.progressed == ["saving_raw_answer"]


def test_legacy_five_part_binding_still_refreshes_normally():
    class Store(BaseStore):
        def progress_bound(
            self, request_id, worker, input_hash, request, stage=None
        ):
            self.progressed.append(stage)
            return True

    store = Store()
    task = bound_task()
    CONTEXT.task = (
        store,
        task["request_id"],
        str(uuid4()),
        task["input_hash"],
        task["request"],
    )
    try:
        checkpoint("legacy-compatible")
    finally:
        CONTEXT.task = None

    assert store.progressed == ["legacy-compatible"]


def test_layer166_release_marker_is_continuous():
    source = open("api/server.py", encoding="utf-8").read()
    assert source.count('"release_layer": 166') == 2
    assert source.count("release_layer=166") == 1
