from types import SimpleNamespace

import core.cognition.durable_tasks as durable
from core.cognition.durable_tasks import TaskRunner, TaskStore


class ReaperClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        outcome = self.outcomes.pop(0)

        class Query:
            def execute(_self):
                if isinstance(outcome, Exception):
                    raise outcome
                return SimpleNamespace(data=outcome)

        return Query()


def test_reaper_runs_once_per_process_cadence(monkeypatch):
    client = ReaperClient([0, 0])
    runner = TaskRunner(
        TaskStore(client),
        lambda request: {"reply": "unused"},
        reaper_interval_seconds=30,
        reaper_failure_backoff_seconds=60,
    )
    times = iter([100.0, 100.0, 105.0, 131.0, 131.0])
    monkeypatch.setattr(durable.time, "monotonic", lambda: next(times))

    assert runner._maybe_reap_expired() is True
    assert runner._maybe_reap_expired() is False
    assert runner._maybe_reap_expired() is True

    assert client.calls == [
        ("l_task_reap_expired", {"p_limit": 100}),
        ("l_task_reap_expired", {"p_limit": 100}),
    ]


def test_reaper_failure_uses_longer_backoff(monkeypatch):
    client = ReaperClient([ConnectionError("synthetic"), 0])
    runner = TaskRunner(
        TaskStore(client),
        lambda request: {"reply": "unused"},
        reaper_interval_seconds=30,
        reaper_failure_backoff_seconds=60,
    )
    times = iter([100.0, 100.0, 101.0, 120.0, 162.0, 162.0])
    monkeypatch.setattr(durable.time, "monotonic", lambda: next(times))

    assert runner._maybe_reap_expired() is False
    assert runner._maybe_reap_expired() is False
    assert runner._maybe_reap_expired() is True

    assert len(client.calls) == 2


class OneLoopStop:
    def __init__(self):
        self.waits = 0

    def is_set(self):
        return self.waits >= 1

    def set(self):
        self.waits = 1

    def wait(self, _timeout=None):
        self.waits += 1
        return self.is_set()


class ReaperFailsButClaimWorks(TaskStore):
    def __init__(self):
        self.claims = []
        self._claim_tokens = {}
        self._claim_token_lock = durable.threading.Lock()

    def reap_expired(self, limit=100):
        raise ConnectionError("synthetic maintenance failure")

    def claim(self, worker, claim_token=None):
        self.claims.append((worker, claim_token))
        return None


def test_reaper_failure_does_not_block_queue_claim(monkeypatch):
    store = ReaperFailsButClaimWorks()
    runner = TaskRunner(
        store,
        lambda request: {"reply": "unused"},
        reaper_interval_seconds=30,
        reaper_failure_backoff_seconds=60,
    )
    runner.stop_event = OneLoopStop()
    monkeypatch.setattr(durable.time, "monotonic", lambda: 100.0)

    runner.loop()

    assert len(store.claims) == 1
    assert store.claims[0][1] is not None
