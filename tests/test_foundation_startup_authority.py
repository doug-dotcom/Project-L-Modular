from pathlib import Path

from services.foundation_startup_authority import FoundationStartupAuthority


class DeferredThread:
    def __init__(self, *, target, args, name, daemon):
        self.target = target
        self.args = args
        self.name = name
        self.daemon = daemon
        self.started = False
        self.finished = False

    def start(self):
        self.started = True

    def is_alive(self):
        return self.started and not self.finished

    def run(self):
        try:
            self.target(*self.args)
        finally:
            self.finished = True


def thread_factory_recorder(threads):
    def factory(**kwargs):
        thread = DeferredThread(**kwargs)
        threads.append(thread)
        return thread

    return factory


def test_foundation_startup_returns_before_owner_or_remote_calls_and_recovers_busy():
    threads = []
    owner_calls = []
    ensure_calls = []
    waits = []
    transitions = []
    results = [
        {"status": "busy", "retry_after": 7, "refreshed": False},
        {
            "status": "active",
            "delegation_token": "secret-that-must-never-enter-snapshot",
            "refreshed": False,
        },
    ]

    def owner_resolver(db):
        owner_calls.append(db)
        return "11111111-1111-4111-8111-111111111111"

    def ensure_impl(db, owner_id, *, timeout_seconds):
        ensure_calls.append((db, owner_id, timeout_seconds))
        return results.pop(0)

    monitor = FoundationStartupAuthority(
        owner_resolver=owner_resolver,
        ensure_impl=ensure_impl,
        retry_delays_seconds=(2.0, 5.0, 12.0),
        thread_factory=thread_factory_recorder(threads),
        wait_impl=lambda delay: waits.append(delay) or False,
    )

    snapshot = monitor.start("db", on_transition=transitions.append)

    assert snapshot == {
        "status": "checking",
        "attempts": 0,
        "background_retry": True,
        "retry_exhausted": False,
    }
    assert owner_calls == []
    assert ensure_calls == []
    assert len(threads) == 1
    assert threads[0].started is True

    threads[0].run()

    assert len(owner_calls) == 1
    assert len(ensure_calls) == 2
    assert waits == [7.0]
    assert monitor.snapshot() == {
        "status": "active",
        "attempts": 2,
        "background_retry": False,
        "retry_exhausted": False,
    }
    assert [item["status"] for item in transitions] == [
        "checking",
        "busy",
        "active",
    ]
    assert "delegation_token" not in str(monitor.snapshot())
    assert "secret-that-must-never-enter-snapshot" not in str(transitions)


def test_foundation_startup_stops_immediately_on_reconnect_required():
    threads = []
    waits = []
    monitor = FoundationStartupAuthority(
        owner_resolver=lambda db: "11111111-1111-4111-8111-111111111111",
        ensure_impl=lambda *args, **kwargs: {
            "status": "reconnect-required",
            "reason_code": "integration-link-inactive",
        },
        retry_delays_seconds=(1.0, 2.0),
        thread_factory=thread_factory_recorder(threads),
        wait_impl=lambda delay: waits.append(delay) or False,
    )

    monitor.start("db")
    threads[0].run()

    assert waits == []
    assert monitor.snapshot() == {
        "status": "reconnect-required",
        "attempts": 1,
        "background_retry": False,
        "retry_exhausted": False,
    }


def test_foundation_startup_exhausts_retry_safe_failures_with_bounded_attempts():
    threads = []
    calls = []
    waits = []

    def ensure_impl(*args, **kwargs):
        calls.append(True)
        return {"status": "unavailable", "retry_safe": True}

    monitor = FoundationStartupAuthority(
        owner_resolver=lambda db: "11111111-1111-4111-8111-111111111111",
        ensure_impl=ensure_impl,
        retry_delays_seconds=(1.0, 2.0, 3.0),
        thread_factory=thread_factory_recorder(threads),
        wait_impl=lambda delay: waits.append(delay) or False,
    )

    monitor.start("db")
    threads[0].run()

    assert len(calls) == 4
    assert waits == [1.0, 2.0, 3.0]
    assert monitor.snapshot() == {
        "status": "unavailable",
        "attempts": 4,
        "background_retry": False,
        "retry_exhausted": True,
    }


def test_foundation_startup_not_configured_is_safe_and_does_not_spawn_worker():
    threads = []
    monitor = FoundationStartupAuthority(
        thread_factory=thread_factory_recorder(threads),
    )

    snapshot = monitor.start(None)

    assert snapshot == {
        "status": "not_configured",
        "attempts": 0,
        "background_retry": False,
        "retry_exhausted": False,
    }
    assert threads == []


def test_server_wires_foundation_startup_reconciliation_into_health_and_shutdown():
    source = Path("api/server.py").read_text()

    assert "FOUNDATION_STARTUP_AUTHORITY.start(" in source
    assert "on_transition=log_foundation_startup_authority" in source
    assert '"foundation_startup_authority": FOUNDATION_STARTUP_AUTHORITY.snapshot()' in source
    assert "FOUNDATION_STARTUP_AUTHORITY.stop()" in source
