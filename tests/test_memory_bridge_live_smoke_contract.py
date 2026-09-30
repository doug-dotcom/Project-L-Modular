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
            assert path == "/internal/shine-ai/memory/health"
            assert headers["X-Shine-Service-Token"] == "x" * 32
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
        def record_event(self, event_type, payload):
            recorded["event_type"] = event_type
            recorded["payload"] = dict(payload)
            return {
                "recorded": True,
                "event_type": event_type,
                "storage": "railway-redis-volume",
            }

    monkeypatch.setattr(smoke, "_client", lambda: Client())
    monkeypatch.setattr(smoke, "OBSERVABILITY_LIEUTENANT", Observability())

    smoke.main()

    output = capsys.readouterr().out
    assert "Project L memory bridge live smoke: PASS" in output
    assert "records=1" in output
    assert "requests=1" in output
    assert "success_rate=1.0" in output
    assert "latency_ms=12.5" in output
    assert "slo=warming" in output
    assert "history=railway-redis-volume" in output
    assert "SECRET MEMORY CONTENT" not in output
    assert "diving bali" not in output
    assert "11111111-1111-4111-8111-111111111111" not in output

    assert recorded["event_type"] == "memory_bridge_deploy_slo"
    assert recorded["payload"] == {
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
