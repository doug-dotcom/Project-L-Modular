import importlib.util
from pathlib import Path


SCRIPT = Path("scripts/verify_memory_bridge_live.py")


def load_smoke_module():
    spec = importlib.util.spec_from_file_location("verify_memory_bridge_live", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_memory_bridge_live_smoke_prints_receipts_not_memory_content(monkeypatch, capsys):
    smoke = load_smoke_module()

    monkeypatch.setenv("SHINE_AI_MEMORY_TOKEN", "x" * 32)
    monkeypatch.setenv(
        "L_MEMORY_OWNER_ID",
        "11111111-1111-4111-8111-111111111111",
    )

    class Response:
        def __init__(self, body):
            self.status_code = 200
            self._body = body

        def json(self):
            return self._body

    class Client:
        def __init__(self):
            self.requests_total = 0
            self.success_total = 0

        def get(self, path, headers):
            assert headers["X-Shine-Service-Token"] == "x" * 32
            if path == "/internal/shine-ai/memory/health":
                return Response({
                    "source": "project-l",
                    "component": "memory-bridge",
                    "version": "2.2",
                    "status": "ready",
                    "circuit_state": "closed",
                    "retry_after": 0,
                    "failure_streak": 0,
                    "recovery_probe_in_progress": False,
                    "database_configured": True,
                    "database_touched": False,
                    "max_concurrent_rpcs": 2,
                    "rpc_timeout_seconds": 6.0,
                    "rpc_connect_seconds": 3.0,
                    "rpc_pool_seconds": 1.0,
                    "read_only": True,
                    "fail_closed": True,
                    "metrics": {
                        "requests_total": self.requests_total,
                        "success_total": self.success_total,
                        "failure_total": 0,
                        "success_rate": (
                            1.0 if self.success_total else None
                        ),
                        "last_latency_ms": (
                            12.5 if self.success_total else 0.0
                        ),
                        "slo_status": "warming",
                    },
                })

            if path == "/internal/shine-ai/memory/observability":
                return Response({
                    "source": "project-l",
                    "component": "memory-bridge-observability",
                    "version": "1.0",
                    "database_touched": False,
                    "memory_content_included": False,
                    "process_metrics": {},
                    "durable": {
                        "storage": "railway-redis-volume",
                        "targets": {
                            "min_samples": 20,
                            "availability": 0.99,
                            "latency_ms": 3000.0,
                            "history_limit": 100,
                        },
                        "deployment": {
                            "status": "warming",
                            "samples": 3,
                            "successes": 3,
                            "failures": 0,
                            "availability": 1.0,
                            "ewma_latency_ms": 21.6,
                        },
                        "runtime": {
                            "status": "warming",
                            "samples": 2,
                            "successes": 2,
                            "failures": 0,
                            "availability": 1.0,
                            "mean_latency_ms": 100.0,
                            "periodic_rollups": 1,
                            "shutdown_rollups": 0,
                            "canary_rollups": 1,
                            "recovery_successes_since_last_failure": 2,
                            "recovery_samples_since_last_failure": 2,
                            "qualified_recovery_successes": 2,
                            "qualified_recovery_samples": 2,
                            "recovery_state": "recovering",
                            "operational_state": "warming",
                        },
                    },
                })

            raise AssertionError(f"unexpected GET path: {path}")

        def post(self, path, headers, json):
            assert path == "/internal/shine-ai/memory/retrieve"
            assert json["query"] == "diving bali"
            assert json["scopes"] == ["sport"]
            self.requests_total += 1
            self.success_total += 1
            return Response({
                "source": "project-l",
                "engine": "project-l-memory-context-v2",
                "version": "2.2",
                "recall_active": True,
                "records": [{
                    "id": "memory_sport:1",
                    "text": "SECRET MEMORY CONTENT",
                    "tags": ["sport"],
                    "priority": "normal",
                }],
                "receipt": {
                    "status": "ok",
                    "records_returned": 1,
                    "owner_bound": True,
                    "permission_scoped": True,
                    "bounded": True,
                    "read_only": True,
                    "legacy_global_search_used": False,
                    "legacy_rpc_fallback_used": False,
                    "query_binding": "server-verified",
                    "query_contract_version": "2",
                    "query_key": "a" * 32,
                },
            })

    recorded = {}

    class Observability:
        def __init__(self):
            self.events = [
                {
                    "event_type": "memory_bridge_deploy_slo",
                    "payload": {
                        "latency_ms": 25.0,
                        # Legacy success event: no explicit outcome.
                    },
                },
                {
                    "event_type": "memory_bridge_deploy_slo",
                    "payload": {
                        "outcome": "success",
                        "latency_ms": 20.0,
                    },
                },
                {
                    "event_type": "memory_bridge_runtime_rollup",
                    "payload": {
                        "rollup_kind": "periodic",
                        "requests": 2,
                        "successes": 2,
                        "failures": 0,
                        "availability": 1.0,
                        "mean_latency_ms": 100.0,
                    },
                },
            ]

        def record_event(self, event_type, payload):
            recorded["event_type"] = event_type
            recorded["payload"] = dict(payload)
            self.events.append({
                "event_type": event_type,
                "payload": dict(payload),
            })
            return {
                "recorded": True,
                "event_type": event_type,
                "storage": "railway-redis-volume",
            }

        def load_events(self):
            return list(self.events)

    observability = Observability()

    def flush_runtime_rollup(*, force, synchronous, rollup_kind):
        assert force is True
        assert synchronous is True
        assert rollup_kind == "canary"
        observability.events.append({
            "event_type": "memory_bridge_runtime_rollup",
            "payload": {
                "rollup_kind": "canary",
                "requests": 1,
                "successes": 1,
                "failures": 0,
                "availability": 1.0,
                "mean_latency_ms": 12.5,
            },
        })
        return {
            "scheduled": True,
            "recorded": True,
            "storage": "railway-redis-volume",
        }

    monkeypatch.setattr(smoke, "_client", lambda: Client())
    monkeypatch.setattr(smoke, "OBSERVABILITY_LIEUTENANT", observability)
    monkeypatch.setattr(
        smoke.bridge,
        "_flush_runtime_rollup",
        flush_runtime_rollup,
    )

    smoke.main()

    output = capsys.readouterr().out
    assert "Project L memory bridge live smoke: PASS" in output
    assert "records=1" in output
    assert "requests=1" in output
    assert "success_rate=1.0" in output
    assert "latency_ms=12.5" in output
    assert "slo=warming" in output
    assert "history=railway-redis-volume" in output
    assert "durable_slo=warming" in output
    assert "durable_samples=3" in output
    assert "durable_successes=3" in output
    assert "durable_failures=0" in output
    assert "durable_availability=1.0" in output
    assert "runtime_rollup=railway-redis-volume" in output
    assert "runtime_slo=warming" in output
    assert "runtime_samples=2" in output
    assert "runtime_successes=2" in output
    assert "runtime_failures=0" in output
    assert "runtime_availability=1.0" in output
    assert "runtime_mean_latency_ms=100.0" in output
    assert "runtime_periodic_rollups=1" in output
    assert "runtime_shutdown_rollups=0" in output
    assert "runtime_canary_rollups=1" in output
    assert "runtime_recovery_state=recovering" in output
    assert "runtime_recovery_successes=2" in output
    assert "runtime_qualified_recovery_successes=2" in output
    assert "runtime_operational_state=warming" in output
    assert "observability_api=verified" in output
    assert "SECRET MEMORY CONTENT" not in output
    assert "diving bali" not in output
    assert "11111111-1111-4111-8111-111111111111" not in output

    assert recorded["event_type"] == "memory_bridge_deploy_slo"
    assert recorded["payload"] == {
        "outcome": "success",
        "circuit_state": "closed",
        "records": 1,
        "contract_version": "2",
        "telemetry_requests": 1,
        "success_rate": 1.0,
        "latency_ms": 12.5,
        "slo_status": "warming",
    }
    raw_payload = str(recorded["payload"])
    assert "SECRET MEMORY CONTENT" not in raw_payload
    assert "diving bali" not in raw_payload
    assert "11111111-1111-4111-8111-111111111111" not in raw_payload



def test_memory_bridge_live_smoke_persists_failed_canary(monkeypatch, capsys):
    smoke = load_smoke_module()
    events = []

    class FailingClient:
        def get(self, path, headers):
            return type(
                "Response",
                (),
                {"status_code": 503, "json": lambda self: {}},
            )()

    class Observability:
        def record_event(self, event_type, payload):
            events.append({
                "event_type": event_type,
                "payload": dict(payload),
            })
            return {
                "recorded": True,
                "event_type": event_type,
                "storage": "railway-redis-volume",
            }

        def load_events(self):
            return list(events)

    monkeypatch.setenv("SHINE_AI_MEMORY_TOKEN", "x" * 32)
    monkeypatch.setenv(
        "L_MEMORY_OWNER_ID",
        "11111111-1111-4111-8111-111111111111",
    )
    monkeypatch.setattr(smoke, "_client", lambda: FailingClient())
    monkeypatch.setattr(smoke, "OBSERVABILITY_LIEUTENANT", Observability())

    try:
        smoke.main()
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert "health-unavailable" in str(exc)

    assert events == [{
        "event_type": "memory_bridge_deploy_slo",
        "payload": {
            "outcome": "failure",
            "failure_stage": "health-unavailable",
            "records": 0,
            "success_rate": 0.0,
        },
    }]

    output = capsys.readouterr().out
    assert "outcome=failure" in output
    assert "durable_slo=warming" in output
    assert "durable_samples=1" in output
    assert "durable_availability=0.0" in output
    assert "11111111-1111-4111-8111-111111111111" not in output


def test_durable_slo_treats_legacy_events_as_success(monkeypatch):
    smoke = load_smoke_module()

    class Observability:
        def load_events(self):
            return [
                {
                    "event_type": "memory_bridge_deploy_slo",
                    "payload": {"latency_ms": 500.0},
                },
                {
                    "event_type": "memory_bridge_deploy_slo",
                    "payload": {
                        "outcome": "failure",
                        "failure_stage": "retrieval-unavailable",
                    },
                },
            ]

    monkeypatch.setattr(smoke, "OBSERVABILITY_LIEUTENANT", Observability())

    summary = smoke._durable_slo_summary()

    assert summary["samples"] == 2
    assert summary["successes"] == 1
    assert summary["failures"] == 1
    assert summary["availability"] == 0.5
    assert summary["status"] == "warming"


def test_durable_slo_reports_met_and_missed_after_enough_history(monkeypatch):
    smoke = load_smoke_module()

    class Observability:
        events = []

        def load_events(self):
            return list(self.events)

    obs = Observability()
    monkeypatch.setattr(smoke, "OBSERVABILITY_LIEUTENANT", obs)

    obs.events = [
        {
            "event_type": "memory_bridge_deploy_slo",
            "payload": {
                "outcome": "success",
                "latency_ms": 700.0,
            },
        }
        for _ in range(20)
    ]
    met = smoke._durable_slo_summary()
    assert met["status"] == "met"
    assert met["availability"] == 1.0
    assert met["ewma_latency_ms"] == 700.0

    obs.events[-1] = {
        "event_type": "memory_bridge_deploy_slo",
        "payload": {
            "outcome": "failure",
            "failure_stage": "retrieval-unavailable",
        },
    }
    missed = smoke._durable_slo_summary()
    assert missed["status"] == "missed"
    assert missed["successes"] == 19
    assert missed["failures"] == 1
    assert missed["availability"] == 0.95



def test_durable_runtime_slo_excludes_canary_rollups(monkeypatch):
    smoke = load_smoke_module()

    class Observability:
        def load_events(self):
            return [
                {
                    "event_type": "memory_bridge_runtime_rollup",
                    "payload": {
                        "rollup_kind": "canary",
                        "successes": 1,
                        "failures": 0,
                        "mean_latency_ms": 50.0,
                    },
                },
                {
                    "event_type": "memory_bridge_runtime_rollup",
                    "payload": {
                        "rollup_kind": "periodic",
                        "successes": 3,
                        "failures": 1,
                        "mean_latency_ms": 400.0,
                    },
                },
            ]

    monkeypatch.setattr(smoke, "OBSERVABILITY_LIEUTENANT", Observability())

    summary = smoke._durable_runtime_slo_summary()

    assert summary["samples"] == 4
    assert summary["successes"] == 3
    assert summary["failures"] == 1
    assert summary["availability"] == 0.75
    assert summary["mean_latency_ms"] == 400.0
    assert summary["periodic_rollups"] == 1
    assert summary["shutdown_rollups"] == 0
    assert summary["canary_rollups"] == 1
    assert summary["status"] == "warming"


def test_durable_runtime_slo_reports_met_and_missed_after_real_samples(monkeypatch):
    smoke = load_smoke_module()

    class Observability:
        events = []

        def load_events(self):
            return list(self.events)

    obs = Observability()
    monkeypatch.setattr(smoke, "OBSERVABILITY_LIEUTENANT", obs)

    obs.events = [
        {
            "event_type": "memory_bridge_runtime_rollup",
            "payload": {
                "rollup_kind": "periodic",
                "successes": 20,
                "failures": 0,
                "mean_latency_ms": 800.0,
            },
        }
    ]
    met = smoke._durable_runtime_slo_summary()
    assert met["status"] == "met"
    assert met["samples"] == 20
    assert met["availability"] == 1.0
    assert met["mean_latency_ms"] == 800.0

    obs.events = [
        {
            "event_type": "memory_bridge_runtime_rollup",
            "payload": {
                "rollup_kind": "periodic",
                "successes": 19,
                "failures": 1,
                "mean_latency_ms": 800.0,
            },
        }
    ]
    missed_availability = smoke._durable_runtime_slo_summary()
    assert missed_availability["status"] == "missed"
    assert missed_availability["availability"] == 0.95

    obs.events = [
        {
            "event_type": "memory_bridge_runtime_rollup",
            "payload": {
                "rollup_kind": "periodic",
                "successes": 20,
                "failures": 0,
                "mean_latency_ms": 3500.0,
            },
        }
    ]
    missed_latency = smoke._durable_runtime_slo_summary()
    assert missed_latency["status"] == "missed"
    assert missed_latency["mean_latency_ms"] == 3500.0



def test_durable_runtime_slo_counts_shutdown_rollups_as_real_traffic(monkeypatch):
    smoke = load_smoke_module()

    class Observability:
        def load_events(self):
            return [
                {
                    "event_type": "memory_bridge_runtime_rollup",
                    "payload": {
                        "rollup_kind": "periodic",
                        "successes": 2,
                        "failures": 0,
                        "mean_latency_ms": 400.0,
                    },
                },
                {
                    "event_type": "memory_bridge_runtime_rollup",
                    "payload": {
                        "rollup_kind": "shutdown",
                        "successes": 1,
                        "failures": 1,
                        "mean_latency_ms": 600.0,
                    },
                },
                {
                    "event_type": "memory_bridge_runtime_rollup",
                    "payload": {
                        "rollup_kind": "canary",
                        "successes": 1,
                        "failures": 0,
                        "mean_latency_ms": 50.0,
                    },
                },
            ]

    monkeypatch.setattr(smoke, "OBSERVABILITY_LIEUTENANT", Observability())

    summary = smoke._durable_runtime_slo_summary()

    assert summary["samples"] == 4
    assert summary["successes"] == 3
    assert summary["failures"] == 1
    assert summary["availability"] == 0.75
    assert summary["mean_latency_ms"] == 500.0
    assert summary["periodic_rollups"] == 1
    assert summary["shutdown_rollups"] == 1
    assert summary["canary_rollups"] == 1
    assert summary["status"] == "warming"



def test_durable_runtime_slo_reports_recovery_streak_without_erasing_failures(monkeypatch):
    smoke = load_smoke_module()

    class Observability:
        def load_events(self):
            return [
                {
                    "event_type": "memory_bridge_runtime_rollup",
                    "payload": {
                        "rollup_kind": "periodic",
                        "successes": 8,
                        "failures": 2,
                        "mean_latency_ms": 1000.0,
                    },
                },
                {
                    "event_type": "memory_bridge_runtime_rollup",
                    "payload": {
                        "rollup_kind": "periodic",
                        "successes": 2,
                        "failures": 0,
                        "mean_latency_ms": 900.0,
                    },
                },
                {
                    "event_type": "memory_bridge_runtime_rollup",
                    "payload": {
                        "rollup_kind": "shutdown",
                        "successes": 2,
                        "failures": 0,
                        "mean_latency_ms": 800.0,
                    },
                },
            ]

    monkeypatch.setattr(smoke, "OBSERVABILITY_LIEUTENANT", Observability())

    summary = smoke._durable_runtime_slo_summary()

    assert summary["failures"] == 2
    assert summary["availability"] == round(12 / 14, 6)
    assert summary["status"] == "warming"
    assert summary["recovery_successes_since_last_failure"] == 4
    assert summary["recovery_samples_since_last_failure"] == 4
    assert summary["recovery_state"] == "healthy_streak"


def test_durable_runtime_slo_recovery_streak_stops_at_latest_failure(monkeypatch):
    smoke = load_smoke_module()

    class Observability:
        def load_events(self):
            return [
                {
                    "event_type": "memory_bridge_runtime_rollup",
                    "payload": {
                        "rollup_kind": "periodic",
                        "successes": 10,
                        "failures": 0,
                        "mean_latency_ms": 700.0,
                    },
                },
                {
                    "event_type": "memory_bridge_runtime_rollup",
                    "payload": {
                        "rollup_kind": "periodic",
                        "successes": 1,
                        "failures": 1,
                        "mean_latency_ms": 900.0,
                    },
                },
                {
                    "event_type": "memory_bridge_runtime_rollup",
                    "payload": {
                        "rollup_kind": "periodic",
                        "successes": 2,
                        "failures": 0,
                        "mean_latency_ms": 800.0,
                    },
                },
            ]

    monkeypatch.setattr(smoke, "OBSERVABILITY_LIEUTENANT", Observability())

    summary = smoke._durable_runtime_slo_summary()

    assert summary["failures"] == 1
    assert summary["recovery_successes_since_last_failure"] == 2
    assert summary["recovery_state"] == "recovering"



def test_observability_memory_slo_snapshot_exposes_runtime_recovery_streak(tmp_path, monkeypatch):
    from orchestration.lieutenants import observability_lieutenant as module

    lieutenant = module.ObservabilityLieutenant()
    monkeypatch.setattr(
        lieutenant,
        "load_events_with_source",
        lambda: ([
            {
                "event_type": "memory_bridge_runtime_rollup",
                "payload": {
                    "rollup_kind": "periodic",
                    "successes": 8,
                    "failures": 2,
                    "mean_latency_ms": 1000.0,
                },
            },
            {
                "event_type": "memory_bridge_runtime_rollup",
                "payload": {
                    "rollup_kind": "periodic",
                    "successes": 2,
                    "failures": 0,
                    "mean_latency_ms": 800.0,
                },
            },
            {
                "event_type": "memory_bridge_runtime_rollup",
                "payload": {
                    "rollup_kind": "canary",
                    "successes": 99,
                    "failures": 0,
                    "mean_latency_ms": 50.0,
                },
            },
            {
                "event_type": "memory_bridge_runtime_rollup",
                "payload": {
                    "rollup_kind": "shutdown",
                    "successes": 2,
                    "failures": 0,
                    "mean_latency_ms": 700.0,
                },
            },
        ], "railway-redis-volume"),
    )

    runtime = lieutenant.memory_bridge_slo_snapshot()["runtime"]

    assert runtime["failures"] == 2
    assert runtime["recovery_successes_since_last_failure"] == 4
    assert runtime["recovery_samples_since_last_failure"] == 4
    assert runtime["recovery_state"] == "healthy_streak"


def test_durable_runtime_recovery_rejects_slow_success_streak(monkeypatch):
    smoke = load_smoke_module()

    class Observability:
        def load_events(self):
            return [
                {
                    "event_type": "memory_bridge_runtime_rollup",
                    "payload": {
                        "rollup_kind": "periodic",
                        "successes": 20,
                        "failures": 1,
                        "mean_latency_ms": 1000.0,
                    },
                },
                {
                    "event_type": "memory_bridge_runtime_rollup",
                    "payload": {
                        "rollup_kind": "periodic",
                        "successes": 2,
                        "failures": 0,
                        "mean_latency_ms": 3500.0,
                    },
                },
                {
                    "event_type": "memory_bridge_runtime_rollup",
                    "payload": {
                        "rollup_kind": "shutdown",
                        "successes": 2,
                        "failures": 0,
                        "mean_latency_ms": 4000.0,
                    },
                },
            ]

    monkeypatch.setattr(smoke, "OBSERVABILITY_LIEUTENANT", Observability())

    summary = smoke._durable_runtime_slo_summary()

    assert summary["status"] == "missed"
    assert summary["recovery_successes_since_last_failure"] == 4
    assert summary["qualified_recovery_successes"] == 0
    assert summary["recovery_state"] == "latency_degraded"
    assert summary["operational_state"] == "degraded"


def test_observability_marks_historical_miss_as_recovered_observing(monkeypatch):
    from orchestration.lieutenants import observability_lieutenant as module

    lieutenant = module.ObservabilityLieutenant()
    monkeypatch.setattr(
        lieutenant,
        "load_events_with_source",
        lambda: ([
            {
                "event_type": "memory_bridge_runtime_rollup",
                "payload": {
                    "rollup_kind": "periodic",
                    "successes": 20,
                    "failures": 2,
                    "mean_latency_ms": 1000.0,
                },
            },
            {
                "event_type": "memory_bridge_runtime_rollup",
                "payload": {
                    "rollup_kind": "periodic",
                    "successes": 2,
                    "failures": 0,
                    "mean_latency_ms": 800.0,
                },
            },
            {
                "event_type": "memory_bridge_runtime_rollup",
                "payload": {
                    "rollup_kind": "shutdown",
                    "successes": 2,
                    "failures": 0,
                    "mean_latency_ms": 700.0,
                },
            },
        ], "railway-redis-volume"),
    )

    runtime = lieutenant.memory_bridge_slo_snapshot()["runtime"]

    assert runtime["status"] == "missed"
    assert runtime["qualified_recovery_successes"] == 4
    assert runtime["qualified_recovery_samples"] == 4
    assert runtime["recovery_state"] == "healthy_streak"
    assert runtime["operational_state"] == "recovered_observing"

