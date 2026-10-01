from pathlib import Path
import hashlib
import hmac
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.shine_ai_memory as bridge

OWNER = "4ad046b3-06a5-4e62-a3ef-17a4f83dcdde"


def client() -> TestClient:
    app = FastAPI()
    app.include_router(bridge.router)
    return TestClient(app)


def configure(monkeypatch):
    monkeypatch.setenv("SHINE_AI_MEMORY_TOKEN", "x" * 32)
    monkeypatch.setenv(
        "SHINE_AI_MEMORY_HEALTH_ATTESTATION_KEY_ID",
        "health-test-v1",
    )
    monkeypatch.setenv(
        "SHINE_AI_MEMORY_HEALTH_ATTESTATION_KEY",
        "h" * 48,
    )
    monkeypatch.setenv("PROJECT_L_OWNER_ID", OWNER)
    bridge._db_client = None
    bridge._db_transport = None
    bridge._rpc_circuit_open_until = 0.0
    bridge._rpc_failure_streak = 0
    with bridge._rpc_metrics_lock:
        bridge._rpc_metrics.update({
            "requests_total": 0,
            "success_total": 0,
            "failure_total": 0,
            "saturation_rejections": 0,
            "circuit_rejections": 0,
            "recovery_probe_rejections": 0,
            "transient_retries": 0,
            "breaker_open_events": 0,
            "http_timeout_failures": 0,
            "last_latency_ms": 0.0,
            "ewma_latency_ms": 0.0,
            "max_latency_ms": 0.0,
            "last_success_at": 0.0,
            "last_failure_at": 0.0,
        })
    with bridge._runtime_rollup_lock:
        bridge._runtime_rollup_accumulator = (
            bridge._empty_runtime_rollup_accumulator()
        )
        bridge._runtime_rollup_inflight = False
        bridge._runtime_rollup_last_emit_at = bridge.time.monotonic()


def owner_context():
    return {
        "status": "ok",
        "queryContractVersion": "2",
        "scope": {
            "ownerBound": True,
            "quarantineExcluded": True,
            "correctionsPreferred": True,
        },
        "compression": {
            "charBudget": 7200,
            "sourceChars": 1200,
            "returnedChars": 900,
        },
        "matches": [
            {
                "id": "5507",
                "domain": "sport",
                "content": "Diving training memory.",
                "authority": {"class": "direct_user_promoted_memory"},
                "provenance": {
                    "sourceTable": "memory_sport",
                    "sourceId": "5507",
                    "sourceRole": "user",
                    "ownerBound": True,
                },
            },
            {
                "id": "abc",
                "domain": "general",
                "content": "General Shine Dive memory.",
                "authority": {"class": "promoted_memory_unlinked_provenance"},
                "provenance": {
                    "sourceTable": "memory_general",
                    "sourceId": "abc",
                    "sourceRole": "unknown",
                    "ownerBound": True,
                },
            },
            {
                "id": "5391",
                "domain": "recovery",
                "content": "Recovery information must not cross this scope boundary.",
                "authority": {"class": "direct_user_promoted_memory"},
                "provenance": {
                    "sourceTable": "memory_recovery",
                    "sourceId": "5391",
                    "sourceRole": "user",
                    "ownerBound": True,
                },
            },
        ],
    }


def test_retrieval_is_service_authenticated_owner_scoped_and_bounded(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(
        bridge,
        "_owner_context",
        lambda owner_id, query, limit: owner_context(),
    )

    response = client().post(
        "/internal/shine-ai/memory/retrieve",
        headers={"X-Shine-Service-Token": "x" * 32},
        json={
            "app": "shine-dive",
            "user_id": OWNER,
            "query": "What diving qualifications have I completed?",
            "scopes": ["episodic", "sport", "general"],
            "limit": 2,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "project-l"
    assert body["engine"] == "project-l-memory-context-v2"
    assert len(body["records"]) == 2
    assert body["records"][0]["id"] == "memory_sport:5507"
    assert body["records"][0]["priority"] == "high"
    assert all("recovery" not in record["text"].lower() for record in body["records"])
    assert body["receipt"]["owner_bound"] is True
    assert body["receipt"]["permission_scoped"] is True
    assert body["receipt"]["legacy_global_search_used"] is False
    assert body["receipt"]["legacy_rpc_fallback_used"] is False
    assert body["receipt"]["query_contract_version"] == ""
    assert body["receipt"]["unavailable_scopes"] == ["episodic"]
    assert body["receipt"]["read_only"] is True
    assert body["receipt"]["bounded"] is True


def test_invalid_service_token_is_rejected_before_owner_scoped_query(monkeypatch):
    configure(monkeypatch)
    called = {"value": False}

    def should_not_run(owner_id, query, limit):
        called["value"] = True
        return owner_context()

    monkeypatch.setattr(bridge, "_owner_context", should_not_run)

    response = client().post(
        "/internal/shine-ai/memory/retrieve",
        headers={"X-Shine-Service-Token": "wrong"},
        json={
            "app": "shine-dive",
            "user_id": OWNER,
            "query": "Dive history",
            "scopes": ["sport"],
        },
    )

    assert response.status_code == 401
    assert called["value"] is False


def test_owner_and_scope_boundaries_are_enforced(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(
        bridge,
        "_owner_context",
        lambda owner_id, query, limit: owner_context(),
    )

    wrong_owner = client().post(
        "/internal/shine-ai/memory/retrieve",
        headers={"X-Shine-Service-Token": "x" * 32},
        json={
            "app": "shine-dive",
            "user_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "query": "Dive history",
            "scopes": ["sport"],
        },
    )
    assert wrong_owner.status_code == 403

    forbidden_scope = client().post(
        "/internal/shine-ai/memory/retrieve",
        headers={"X-Shine-Service-Token": "x" * 32},
        json={
            "app": "shine-dive",
            "user_id": OWNER,
            "query": "Health history",
            "scopes": ["health"],
        },
    )
    assert forbidden_scope.status_code == 403


def test_broad_recall_is_rejected_before_database_query(monkeypatch):
    configure(monkeypatch)
    called = {"value": False}

    def should_not_run(owner_id, query, limit):
        called["value"] = True
        return owner_context()

    monkeypatch.setattr(bridge, "_owner_context", should_not_run)

    response = client().post(
        "/internal/shine-ai/memory/retrieve",
        headers={"X-Shine-Service-Token": "x" * 32},
        json={
            "app": "shine-dive",
            "user_id": OWNER,
            "query": "Deep recall everything you know about me",
            "scopes": ["sport"],
        },
    )

    assert response.status_code == 422
    assert called["value"] is False



def test_wellness_bridge_is_limited_to_health_scope(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(
        bridge,
        "_owner_context",
        lambda owner_id, query, limit: {
            **owner_context(),
            "matches": [
                {
                    "id": "health-1",
                    "domain": "health",
                    "content": "Reviewed health memory.",
                    "authority": {"class": "direct_user_promoted_memory"},
                    "provenance": {
                        "sourceTable": "memory_health",
                        "sourceId": "health-1",
                        "sourceRole": "user",
                        "ownerBound": True,
                    },
                },
                {
                    "id": "recovery-1",
                    "domain": "recovery",
                    "content": "Recovery information must not cross this scope boundary.",
                    "authority": {"class": "direct_user_promoted_memory"},
                    "provenance": {
                        "sourceTable": "memory_recovery",
                        "sourceId": "recovery-1",
                        "sourceRole": "user",
                        "ownerBound": True,
                    },
                },
            ],
        },
    )

    allowed = client().post(
        "/internal/shine-ai/memory/retrieve",
        headers={"X-Shine-Service-Token": "x" * 32},
        json={
            "app": "shine-wellness",
            "user_id": OWNER,
            "query": "Recall my health history.",
            "scopes": ["health"],
            "limit": 4,
        },
    )
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["receipt"]["requested_scopes"] == ["health"]
    assert [record["tags"][0] for record in body["records"]] == ["health"]
    assert all("Recovery information" not in record["text"] for record in body["records"])

    for denied_scope in ("general", "sport", "recovery", "episodic"):
        denied = client().post(
            "/internal/shine-ai/memory/retrieve",
            headers={"X-Shine-Service-Token": "x" * 32},
            json={
                "app": "shine-wellness",
                "user_id": OWNER,
                "query": "Recall my history.",
                "scopes": [denied_scope],
                "limit": 4,
            },
        )
        assert denied.status_code == 403


def test_daash_bridge_is_limited_to_sport_scope(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(
        bridge,
        "_owner_context",
        lambda owner_id, query, limit: owner_context(),
    )

    allowed = client().post(
        "/internal/shine-ai/memory/retrieve",
        headers={"X-Shine-Service-Token": "x" * 32},
        json={
            "app": "daash",
            "user_id": OWNER,
            "query": "What training history is relevant to this programme?",
            "scopes": ["sport"],
            "limit": 4,
        },
    )

    assert allowed.status_code == 200
    body = allowed.json()
    assert [record["id"] for record in body["records"]] == ["memory_sport:5507"]
    assert body["receipt"]["requested_scopes"] == ["sport"]
    assert body["receipt"]["unavailable_scopes"] == []

    denied = client().post(
        "/internal/shine-ai/memory/retrieve",
        headers={"X-Shine-Service-Token": "x" * 32},
        json={
            "app": "daash",
            "user_id": OWNER,
            "query": "Recall my full history.",
            "scopes": ["episodic"],
            "limit": 4,
        },
    )

    assert denied.status_code == 403


def test_query_terms_are_bounded_and_drop_low_value_words():
    terms = bridge._query_terms(
        "What diving qualifications have I completed in Bali and what did I do?"
    )
    assert "diving" in terms
    assert "qualifications" in terms
    assert "bali" in terms
    assert "what" not in terms
    assert "in" not in terms
    assert len(terms) <= 24


def test_production_bali_probe_keeps_only_discriminating_terms():
    terms = bridge._query_terms(
        "What diving qualifications have I completed in Bali?"
    )
    assert terms == ["diving", "qualifications", "bali"]


def test_database_client_uses_bounded_http1_transport(monkeypatch):
    configure(monkeypatch)
    seen = {}

    class FakeClient:
        pass

    def fake_create(url, key, options=None):
        seen["url"] = url
        seen["key"] = key
        seen["options"] = options
        return FakeClient()

    monkeypatch.setattr(bridge, "create_client", fake_create)
    db = bridge._database()

    assert isinstance(db, FakeClient)
    assert seen["options"].persist_session is False
    assert seen["options"].auto_refresh_token is False
    assert bridge._db_transport is not None
    assert bridge._db_transport.timeout.read == bridge._MEMORY_RPC_TIMEOUT_SECONDS
    assert bridge._db_transport.timeout.write == bridge._MEMORY_RPC_TIMEOUT_SECONDS
    assert bridge._db_transport.timeout.connect == bridge._MEMORY_RPC_CONNECT_SECONDS
    assert bridge._db_transport.timeout.pool == bridge._MEMORY_RPC_POOL_SECONDS


def test_safe_rpc_error_redacts_credential_like_values():
    class Boom(Exception):
        code = "PGRST202"
        message = "token=super-secret authorization:Bearer-thing function missing"

    summary = bridge._safe_rpc_error(Boom())

    assert "PGRST202" in summary
    assert "super-secret" not in summary
    assert "Bearer-thing" not in summary
    assert "[redacted]" in summary


def test_owner_context_retries_pgrst002_once_then_recovers(monkeypatch):
    configure(monkeypatch)
    calls = {"count": 0}
    sleeps = []
    query = "What diving qualifications have I completed?"

    class SchemaCacheUnavailable(Exception):
        code = "PGRST002"
        message = "Could not query the database for the schema cache"

    class Result:
        data = {
            **owner_context(),
            "queryKey": bridge._query_key(bridge._query_terms(query)),
        }

    class Rpc:
        def execute(self):
            calls["count"] += 1
            if calls["count"] == 1:
                raise SchemaCacheUnavailable()
            return Result()

    class Database:
        def rpc(self, name, payload):
            assert name == "project_l_memory_context_service_v2"
            assert payload["p_query_key"] == bridge._query_key(payload["p_terms"])
            return Rpc()

    monkeypatch.setattr(bridge, "_database", lambda: Database())
    monkeypatch.setattr(bridge.time, "sleep", lambda delay: sleeps.append(delay))

    result = bridge._owner_context(OWNER, query, 4)

    assert result["status"] == "ok"
    assert calls["count"] == 2
    assert sleeps == [0.4]
    assert bridge._rpc_circuit_open_until == 0.0


def test_pgrst002_exhaustion_opens_short_circuit(monkeypatch):
    configure(monkeypatch)
    calls = {"count": 0}
    now = {"value": 100.0}

    class SchemaCacheUnavailable(Exception):
        code = "PGRST002"
        message = "Could not query the database for the schema cache"

    class Rpc:
        def execute(self):
            calls["count"] += 1
            raise SchemaCacheUnavailable()

    class Database:
        def rpc(self, name, payload):
            return Rpc()

    monkeypatch.setattr(bridge, "_database", lambda: Database())
    monkeypatch.setattr(bridge.time, "sleep", lambda delay: None)
    monkeypatch.setattr(bridge.time, "monotonic", lambda: now["value"])

    try:
        bridge._owner_context(OWNER, "Dive history", 4)
        assert False, "expected HTTPException"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 503
        assert getattr(exc, "headers", {})["Retry-After"] == "8"

    assert calls["count"] == 2

    try:
        bridge._owner_context(OWNER, "Dive history", 4)
        assert False, "expected circuit HTTPException"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 503
        assert getattr(exc, "headers", {})["Retry-After"] == "8"

    assert calls["count"] == 2


def test_statement_timeout_retries_once_without_opening_schema_circuit(monkeypatch):
    configure(monkeypatch)
    calls = {"count": 0}
    sleeps = []
    query = "Dive history"

    class StatementTimeout(Exception):
        code = "57014"
        message = "canceling statement due to statement timeout"

    class Result:
        data = {
            **owner_context(),
            "queryKey": bridge._query_key(bridge._query_terms(query)),
        }

    class Rpc:
        def execute(self):
            calls["count"] += 1
            if calls["count"] == 1:
                raise StatementTimeout()
            return Result()

    class Database:
        def rpc(self, name, payload):
            return Rpc()

    monkeypatch.setattr(bridge, "_database", lambda: Database())
    monkeypatch.setattr(bridge.time, "sleep", lambda delay: sleeps.append(delay))

    result = bridge._owner_context(OWNER, query, 4)

    assert result["status"] == "ok"
    assert calls["count"] == 2
    assert sleeps == [0.2]
    assert bridge._rpc_circuit_open_until == 0.0



def test_owner_context_fails_closed_when_v2_function_is_missing(monkeypatch):
    configure(monkeypatch)
    calls = []

    class FunctionMissing(Exception):
        code = "PGRST202"
        message = "Could not find the function public.project_l_memory_context_service_v2"

    class MissingRpc:
        def execute(self):
            raise FunctionMissing()

    class Database:
        def rpc(self, name, payload):
            calls.append(name)
            return MissingRpc()

    monkeypatch.setattr(bridge, "_database", lambda: Database())

    try:
        bridge._owner_context(OWNER, "Dive history", 4)
        assert False, "expected HTTPException"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 503

    assert calls == ["project_l_memory_context_service_v2"]


def test_owner_context_rejects_mismatched_server_query_key(monkeypatch):
    configure(monkeypatch)

    class Rpc:
        def execute(self):
            return type("Result", (), {
                "data": {**owner_context(), "queryKey": "wrong-cohort"}
            })()

    class Database:
        def rpc(self, name, payload):
            assert name == "project_l_memory_context_service_v2"
            return Rpc()

    monkeypatch.setattr(bridge, "_database", lambda: Database())

    try:
        bridge._owner_context(OWNER, "Dive history", 4)
        assert False, "expected HTTPException"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 503
        assert "query binding" in str(getattr(exc, "detail", "")).lower()



def test_memory_bridge_bulkhead_fails_closed_before_database_query(monkeypatch):
    configure(monkeypatch)
    called = {"database": 0}

    class BusyBulkhead:
        def acquire(self, timeout):
            assert timeout == bridge._RPC_BULKHEAD_WAIT_SECONDS
            return False

        def release(self):
            raise AssertionError("unacquired bulkhead must not be released")

    def should_not_run():
        called["database"] += 1
        raise AssertionError("database must not be touched when bulkhead is full")

    monkeypatch.setattr(bridge, "_rpc_bulkhead", BusyBulkhead())
    monkeypatch.setattr(bridge, "_database", should_not_run)

    try:
        bridge._owner_context(OWNER, "Dive history", 4)
        assert False, "expected HTTPException"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 503
        assert getattr(exc, "headers", {})["Retry-After"] == "1"
        assert "saturated" in str(getattr(exc, "detail", "")).lower()

    assert called["database"] == 0


def test_memory_bridge_bulkhead_releases_slot_after_rpc_error(monkeypatch):
    configure(monkeypatch)
    state = {"acquires": 0, "releases": 0}

    class Bulkhead:
        def acquire(self, timeout):
            state["acquires"] += 1
            return True

        def release(self):
            state["releases"] += 1

    class PermissionFailure(Exception):
        code = "42501"
        message = "permission denied"

    class Rpc:
        def execute(self):
            raise PermissionFailure()

    class Database:
        def rpc(self, name, payload):
            return Rpc()

    monkeypatch.setattr(bridge, "_rpc_bulkhead", Bulkhead())
    monkeypatch.setattr(bridge, "_database", lambda: Database())

    try:
        bridge._owner_context(OWNER, "Dive history", 4)
        assert False, "expected HTTPException"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 503

    assert state == {"acquires": 1, "releases": 1}


def test_repeated_schema_failures_expand_circuit_backoff(monkeypatch):
    configure(monkeypatch)
    now = {"value": 100.0}
    monkeypatch.setattr(bridge.time, "monotonic", lambda: now["value"])

    assert bridge._escalate_rpc_circuit() == 8
    assert bridge._rpc_circuit_retry_after() == 8
    assert bridge._rpc_failure_streak == 1

    now["value"] = 109.0
    assert bridge._escalate_rpc_circuit() == 16
    assert bridge._rpc_circuit_retry_after() == 16
    assert bridge._rpc_failure_streak == 2

    now["value"] = 126.0
    assert bridge._escalate_rpc_circuit() == 32
    assert bridge._rpc_circuit_retry_after() == 32
    assert bridge._rpc_failure_streak == 3

    now["value"] = 159.0
    assert bridge._escalate_rpc_circuit() == 60
    assert bridge._rpc_circuit_retry_after() == 60
    assert bridge._rpc_failure_streak == 4

    bridge._close_rpc_circuit()
    assert bridge._rpc_circuit_retry_after() == 0
    assert bridge._rpc_failure_streak == 0



def test_half_open_bridge_allows_only_one_recovery_probe(monkeypatch):
    configure(monkeypatch)
    now = {"value": 200.0}
    bridge._rpc_failure_streak = 2
    bridge._rpc_circuit_open_until = 199.0

    class ProbeBusy:
        def acquire(self, blocking=False):
            assert blocking is False
            return False

        def release(self):
            raise AssertionError("busy probe must not be released")

    called = {"database": 0}

    def should_not_run():
        called["database"] += 1
        raise AssertionError("database must not be touched while recovery probe is busy")

    monkeypatch.setattr(bridge.time, "monotonic", lambda: now["value"])
    monkeypatch.setattr(bridge, "_rpc_half_open_probe", ProbeBusy())
    monkeypatch.setattr(bridge, "_database", should_not_run)

    try:
        bridge._owner_context(OWNER, "Dive history", 4)
        assert False, "expected HTTPException"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 503
        assert getattr(exc, "headers", {})["Retry-After"] == "1"
        assert "recovery probe" in str(getattr(exc, "detail", "")).lower()

    assert called["database"] == 0


def test_successful_half_open_probe_resets_breaker(monkeypatch):
    configure(monkeypatch)
    now = {"value": 300.0}
    bridge._rpc_failure_streak = 3
    bridge._rpc_circuit_open_until = 299.0
    state = {"probe_acquires": 0, "probe_releases": 0}
    query = "Dive history"

    class Probe:
        def acquire(self, blocking=False):
            state["probe_acquires"] += 1
            return True

        def release(self):
            state["probe_releases"] += 1

    class Result:
        data = {
            **owner_context(),
            "queryKey": bridge._query_key(bridge._query_terms(query)),
        }

    class Rpc:
        def execute(self):
            return Result()

    class Database:
        def rpc(self, name, payload):
            assert name == "project_l_memory_context_service_v2"
            return Rpc()

    monkeypatch.setattr(bridge.time, "monotonic", lambda: now["value"])
    monkeypatch.setattr(bridge, "_rpc_half_open_probe", Probe())
    monkeypatch.setattr(bridge, "_database", lambda: Database())

    result = bridge._owner_context(OWNER, query, 4)

    assert result["status"] == "ok"
    assert state == {"probe_acquires": 1, "probe_releases": 1}
    assert bridge._rpc_failure_streak == 0
    assert bridge._rpc_circuit_open_until == 0.0



def test_http_timeout_retries_once_then_opens_adaptive_circuit(monkeypatch):
    configure(monkeypatch)
    calls = {"count": 0}
    now = {"value": 400.0}
    sleeps = []

    class Rpc:
        def execute(self):
            calls["count"] += 1
            raise bridge.httpx.ReadTimeout("database read timed out")

    class Database:
        def rpc(self, name, payload):
            return Rpc()

    monkeypatch.setattr(bridge, "_database", lambda: Database())
    monkeypatch.setattr(bridge.time, "sleep", lambda delay: sleeps.append(delay))
    monkeypatch.setattr(bridge.time, "monotonic", lambda: now["value"])

    try:
        bridge._owner_context(OWNER, "Dive history", 4)
        assert False, "expected HTTPException"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 503
        assert getattr(exc, "headers", {})["Retry-After"] == "8"

    assert calls["count"] == 2
    assert sleeps == [0.25]
    assert bridge._rpc_failure_streak == 1
    assert bridge._rpc_circuit_retry_after() == 8



def test_memory_bridge_health_is_authenticated_and_zero_database_touch(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    called = {"database": 0}

    def should_not_run():
        called["database"] += 1
        raise AssertionError("health endpoint must not touch Supabase")

    monkeypatch.setattr(bridge, "_database", should_not_run)

    response = client().get(
        "/internal/shine-ai/memory/health",
        headers={"X-Shine-Service-Token": "x" * 32},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "project-l"
    assert body["component"] == "memory-bridge"
    assert body["query_contract_version"] == bridge._QUERY_CONTRACT_VERSION
    assert body["retrieval_contract_sha256"] == (
        bridge.memory_retrieval_contract_sha256()
    )
    assert body["retrieval_contract_sha256"] == (
        "caf74ae7d02551b093a11699493b4eaa9185e9c0f3b813644af260d9c0d674ae"
    )
    assert body["status"] == "ready"
    assert body["circuit_state"] == "closed"
    assert body["retry_after"] == 0
    assert body["failure_streak"] == 0
    assert body["database_configured"] is True
    assert body["database_touched"] is False
    assert body["max_concurrent_rpcs"] == 2
    assert body["rpc_timeout_seconds"] == 6.0
    assert body["rpc_connect_seconds"] == 3.0
    assert body["rpc_pool_seconds"] == 1.0
    assert body["read_only"] is True
    assert body["fail_closed"] is True
    assert body["attestation"] is None
    assert called["database"] == 0

    denied = client().get(
        "/internal/shine-ai/memory/health",
        headers={"X-Shine-Service-Token": "wrong"},
    )
    assert denied.status_code == 401
    assert called["database"] == 0


def test_memory_bridge_health_reports_open_and_half_open_states(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    now = {"value": 500.0}
    monkeypatch.setattr(bridge.time, "monotonic", lambda: now["value"])

    bridge._rpc_failure_streak = 2
    bridge._rpc_circuit_open_until = 516.0

    opened = client().get(
        "/internal/shine-ai/memory/health",
        headers={"X-Shine-Service-Token": "x" * 32},
    )
    assert opened.status_code == 200
    open_body = opened.json()
    assert open_body["status"] == "protected"
    assert open_body["circuit_state"] == "open"
    assert open_body["retry_after"] == 16
    assert open_body["failure_streak"] == 2

    now["value"] = 517.0
    half_open = client().get(
        "/internal/shine-ai/memory/health",
        headers={"X-Shine-Service-Token": "x" * 32},
    )
    assert half_open.status_code == 200
    half_body = half_open.json()
    assert half_body["status"] == "protected"
    assert half_body["circuit_state"] == "half-open"
    assert half_body["retry_after"] == 0
    assert half_body["failure_streak"] == 2


def test_memory_bridge_health_reports_degraded_when_database_not_configured(monkeypatch):
    configure(monkeypatch)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_KEY", raising=False)

    response = client().get(
        "/internal/shine-ai/memory/health",
        headers={"X-Shine-Service-Token": "x" * 32},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database_configured"] is False
    assert body["database_touched"] is False



def test_owner_context_rejects_mismatched_query_contract_version(monkeypatch):
    configure(monkeypatch)
    query = "Dive history"

    class Rpc:
        def execute(self):
            return type("Result", (), {
                "data": {
                    **owner_context(),
                    "queryKey": bridge._query_key(bridge._query_terms(query)),
                    "queryContractVersion": "1",
                }
            })()

    class Database:
        def rpc(self, name, payload):
            assert name == "project_l_memory_context_service_v2"
            return Rpc()

    monkeypatch.setattr(bridge, "_database", lambda: Database())

    try:
        bridge._owner_context(OWNER, query, 4)
        assert False, "expected HTTPException"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 503
        assert "query contract" in str(getattr(exc, "detail", "")).lower()



def test_memory_bridge_metrics_record_success_without_query_or_memory_content(
    monkeypatch,
    capsys,
):
    configure(monkeypatch)
    query = "Private diving phrase"
    secret_memory = "DO NOT LOG THIS MEMORY"

    class Result:
        data = {
            **owner_context(),
            "queryKey": bridge._query_key(bridge._query_terms(query)),
            "queryContractVersion": "2",
            "matches": [{
                "id": "1",
                "domain": "sport",
                "content": secret_memory,
                "provenance": {
                    "sourceTable": "memory_sport",
                    "sourceId": "1",
                    "sourceRole": "user",
                },
            }],
        }

    class Rpc:
        def execute(self):
            return Result()

    class Database:
        def rpc(self, name, payload):
            return Rpc()

    monkeypatch.setattr(bridge, "_database", lambda: Database())

    result = bridge._owner_context(OWNER, query, 4)
    assert result["status"] == "ok"

    metrics = bridge._rpc_metrics_snapshot()
    assert metrics["requests_total"] == 1
    assert metrics["success_total"] == 1
    assert metrics["failure_total"] == 0
    assert metrics["success_rate"] == 1.0
    assert metrics["last_latency_ms"] >= 0
    assert metrics["ewma_latency_ms"] >= 0
    assert metrics["max_latency_ms"] >= metrics["last_latency_ms"]

    output = capsys.readouterr().out
    assert "SHINE_AI_MEMORY_SLO outcome=success" in output
    assert query not in output
    assert secret_memory not in output
    assert OWNER not in output


def test_memory_bridge_metrics_count_circuit_rejection(monkeypatch):
    configure(monkeypatch)
    now = {"value": 1000.0}
    bridge._rpc_failure_streak = 1
    bridge._rpc_circuit_open_until = 1008.0
    monkeypatch.setattr(bridge.time, "monotonic", lambda: now["value"])

    try:
        bridge._owner_context(OWNER, "Dive history", 4)
        assert False, "expected HTTPException"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 503

    metrics = bridge._rpc_metrics_snapshot()
    assert metrics["requests_total"] == 1
    assert metrics["success_total"] == 0
    assert metrics["failure_total"] == 1
    assert metrics["circuit_rejections"] == 1
    assert metrics["success_rate"] == 0.0


def test_memory_bridge_health_exposes_privacy_safe_metrics(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    with bridge._rpc_metrics_lock:
        bridge._rpc_metrics["requests_total"] = 8
        bridge._rpc_metrics["success_total"] = 7
        bridge._rpc_metrics["failure_total"] = 1
        bridge._rpc_metrics["transient_retries"] = 2
        bridge._rpc_metrics["last_latency_ms"] = 12.5
        bridge._rpc_metrics["ewma_latency_ms"] = 10.0
        bridge._rpc_metrics["max_latency_ms"] = 30.0

    response = client().get(
        "/internal/shine-ai/memory/health",
        headers={"X-Shine-Service-Token": "x" * 32},
    )

    assert response.status_code == 200
    metrics = response.json()["metrics"]
    assert metrics["requests_total"] == 8
    assert metrics["success_total"] == 7
    assert metrics["failure_total"] == 1
    assert metrics["success_rate"] == 0.875
    assert metrics["transient_retries"] == 2
    assert metrics["last_latency_ms"] == 12.5
    assert "query" not in metrics
    assert "owner" not in metrics
    assert "memory" not in metrics



def test_memory_bridge_slo_stays_warming_until_minimum_sample_count(monkeypatch):
    configure(monkeypatch)
    with bridge._rpc_metrics_lock:
        bridge._rpc_metrics["requests_total"] = 19
        bridge._rpc_metrics["success_total"] = 19
        bridge._rpc_metrics["failure_total"] = 0
        bridge._rpc_metrics["ewma_latency_ms"] = 100.0

    metrics = bridge._rpc_metrics_snapshot()

    assert metrics["slo_status"] == "warming"
    assert metrics["slo_min_samples"] == 20
    assert metrics["slo_availability_target"] == 0.99
    assert metrics["slo_ewma_latency_target_ms"] == 3000.0


def test_memory_bridge_slo_reports_met_after_enough_good_samples(monkeypatch):
    configure(monkeypatch)
    with bridge._rpc_metrics_lock:
        bridge._rpc_metrics["requests_total"] = 100
        bridge._rpc_metrics["success_total"] = 99
        bridge._rpc_metrics["failure_total"] = 1
        bridge._rpc_metrics["ewma_latency_ms"] = 750.0

    metrics = bridge._rpc_metrics_snapshot()

    assert metrics["success_rate"] == 0.99
    assert metrics["slo_status"] == "met"


def test_memory_bridge_slo_reports_missed_for_availability_or_latency(monkeypatch):
    configure(monkeypatch)
    with bridge._rpc_metrics_lock:
        bridge._rpc_metrics["requests_total"] = 100
        bridge._rpc_metrics["success_total"] = 98
        bridge._rpc_metrics["failure_total"] = 2
        bridge._rpc_metrics["ewma_latency_ms"] = 500.0

    assert bridge._rpc_metrics_snapshot()["slo_status"] == "missed"

    with bridge._rpc_metrics_lock:
        bridge._rpc_metrics["success_total"] = 100
        bridge._rpc_metrics["failure_total"] = 0
        bridge._rpc_metrics["ewma_latency_ms"] = 3500.0

    assert bridge._rpc_metrics_snapshot()["slo_status"] == "missed"



def test_runtime_rollup_waits_for_interval_and_flushes_aggregate(monkeypatch):
    configure(monkeypatch)
    now = {"value": 1000.0}
    recorded = []

    monkeypatch.setattr(bridge.time, "monotonic", lambda: now["value"])

    with bridge._runtime_rollup_lock:
        bridge._runtime_rollup_last_emit_at = 1000.0

    bridge._metric_increment("requests_total")
    with bridge._runtime_rollup_lock:
        bridge._runtime_rollup_accumulator["successes"] = 1
        bridge._runtime_rollup_accumulator["latency_sum_ms"] = 750.0
        bridge._runtime_rollup_accumulator["latency_max_ms"] = 750.0

    monkeypatch.setattr(
        bridge,
        "_persist_runtime_rollup",
        lambda snapshot: recorded.append(dict(snapshot)) or {
            "recorded": True,
            "storage": "railway-redis-volume",
        },
    )

    before_due = bridge._flush_runtime_rollup(
        force=False,
        synchronous=True,
    )
    assert before_due["scheduled"] is False
    assert recorded == []

    now["value"] = 1301.0
    due = bridge._flush_runtime_rollup(
        force=False,
        synchronous=True,
    )
    assert due["scheduled"] is True
    assert due["recorded"] is True
    assert len(recorded) == 1
    assert recorded[0]["requests"] == 1
    assert recorded[0]["successes"] == 1
    assert recorded[0]["failures"] == 0
    assert recorded[0]["latency_sum_ms"] == 750.0
    assert recorded[0]["rollup_kind"] == "periodic"


def test_runtime_rollup_background_path_does_not_persist_on_request_thread(monkeypatch):
    configure(monkeypatch)
    now = {"value": 2000.0}
    calls = []

    monkeypatch.setattr(bridge.time, "monotonic", lambda: now["value"])
    with bridge._runtime_rollup_lock:
        bridge._runtime_rollup_last_emit_at = 1600.0
        bridge._runtime_rollup_accumulator["requests"] = 1
        bridge._runtime_rollup_accumulator["successes"] = 1
        bridge._runtime_rollup_accumulator["latency_sum_ms"] = 50.0
        bridge._runtime_rollup_accumulator["latency_max_ms"] = 50.0

    class FakeThread:
        def __init__(self, *, target, args, name, daemon):
            calls.append({
                "target": target,
                "args": args,
                "name": name,
                "daemon": daemon,
            })

        def start(self):
            calls[-1]["started"] = True

    monkeypatch.setattr(bridge.threading, "Thread", FakeThread)

    result = bridge._flush_runtime_rollup()

    assert result == {
        "scheduled": True,
        "recorded": False,
        "storage": "background",
    }
    assert len(calls) == 1
    assert calls[0]["target"] is bridge._persist_runtime_rollup
    assert calls[0]["name"] == "memory-bridge-runtime-rollup"
    assert calls[0]["daemon"] is True
    assert calls[0]["started"] is True


def test_runtime_rollup_requeues_when_durable_storage_is_unavailable(monkeypatch):
    configure(monkeypatch)

    class Observability:
        def record_event(self, event_type, payload):
            assert event_type == "memory_bridge_runtime_rollup"
            return {
                "recorded": True,
                "event_type": event_type,
                "storage": "local-file",
            }

    import orchestration.lieutenants.observability_lieutenant as obs_module
    monkeypatch.setattr(
        obs_module,
        "OBSERVABILITY_LIEUTENANT",
        Observability(),
    )

    snapshot = {
        "requests": 3,
        "successes": 2,
        "failures": 1,
        "latency_sum_ms": 900.0,
        "latency_max_ms": 500.0,
        "saturation_rejections": 1,
        "circuit_rejections": 0,
        "recovery_probe_rejections": 0,
        "transient_retries": 1,
        "breaker_open_events": 0,
        "http_timeout_failures": 0,
        "window_seconds": 300.0,
        "rollup_kind": "periodic",
    }
    with bridge._runtime_rollup_lock:
        bridge._runtime_rollup_inflight = True

    result = bridge._persist_runtime_rollup(snapshot)

    assert result["storage"] == "local-file"
    with bridge._runtime_rollup_lock:
        pending = dict(bridge._runtime_rollup_accumulator)
        assert bridge._runtime_rollup_inflight is False

    assert pending["requests"] == 3
    assert pending["successes"] == 2
    assert pending["failures"] == 1
    assert pending["latency_sum_ms"] == 900.0
    assert pending["latency_max_ms"] == 500.0
    assert pending["saturation_rejections"] == 1
    assert pending["transient_retries"] == 1


def test_runtime_rollup_payload_contains_only_aggregate_operational_data():
    payload = bridge._runtime_rollup_payload({
        "requests": 4,
        "successes": 3,
        "failures": 1,
        "latency_sum_ms": 1200.0,
        "latency_max_ms": 600.0,
        "saturation_rejections": 0,
        "circuit_rejections": 1,
        "recovery_probe_rejections": 0,
        "transient_retries": 2,
        "breaker_open_events": 1,
        "http_timeout_failures": 0,
        "window_seconds": 300.0,
        "rollup_kind": "periodic",
    })

    assert payload["availability"] == 0.75
    assert payload["mean_latency_ms"] == 300.0
    assert payload["max_latency_ms"] == 600.0
    assert payload["rollup_kind"] == "periodic"
    assert all(
        forbidden not in str(payload).lower()
        for forbidden in (
            "query",
            "owner",
            "memory text",
            "token",
            "secret",
        )
    )



def test_shutdown_flush_persists_pending_runtime_rollup(monkeypatch):
    configure(monkeypatch)
    recorded = []

    with bridge._runtime_rollup_lock:
        bridge._runtime_rollup_accumulator["requests"] = 2
        bridge._runtime_rollup_accumulator["successes"] = 2
        bridge._runtime_rollup_accumulator["latency_sum_ms"] = 900.0
        bridge._runtime_rollup_accumulator["latency_max_ms"] = 500.0
        bridge._runtime_rollup_inflight = False

    def persist(snapshot):
        recorded.append(dict(snapshot))
        with bridge._runtime_rollup_lock:
            bridge._runtime_rollup_inflight = False
        return {
            "recorded": True,
            "storage": "railway-redis-volume",
        }

    monkeypatch.setattr(bridge, "_persist_runtime_rollup", persist)

    result = bridge.flush_memory_runtime_rollup_on_shutdown()

    assert result["scheduled"] is True
    assert result["recorded"] is True
    assert result["storage"] == "railway-redis-volume"
    assert len(recorded) == 1
    assert recorded[0]["rollup_kind"] == "shutdown"
    assert recorded[0]["requests"] == 2
    assert recorded[0]["successes"] == 2
    assert recorded[0]["failures"] == 0
    assert recorded[0]["latency_sum_ms"] == 900.0


def test_shutdown_flush_waits_for_inflight_rollup_then_flushes_requeued_metrics(
    monkeypatch,
):
    configure(monkeypatch)
    state = {"now": 1000.0, "sleep_calls": 0}
    recorded = []

    with bridge._runtime_rollup_lock:
        bridge._runtime_rollup_inflight = True

    def fake_monotonic():
        return state["now"]

    def fake_sleep(delay):
        state["sleep_calls"] += 1
        state["now"] += delay
        if state["sleep_calls"] == 1:
            with bridge._runtime_rollup_lock:
                bridge._runtime_rollup_inflight = False
                bridge._runtime_rollup_accumulator["requests"] = 1
                bridge._runtime_rollup_accumulator["failures"] = 1
                bridge._runtime_rollup_accumulator["latency_sum_ms"] = 250.0
                bridge._runtime_rollup_accumulator["latency_max_ms"] = 250.0

    def persist(snapshot):
        recorded.append(dict(snapshot))
        with bridge._runtime_rollup_lock:
            bridge._runtime_rollup_inflight = False
        return {
            "recorded": True,
            "storage": "railway-redis-volume",
        }

    monkeypatch.setattr(bridge.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(bridge.time, "sleep", fake_sleep)
    monkeypatch.setattr(bridge, "_persist_runtime_rollup", persist)

    result = bridge.flush_memory_runtime_rollup_on_shutdown()

    assert state["sleep_calls"] >= 1
    assert result["recorded"] is True
    assert recorded[0]["rollup_kind"] == "shutdown"
    assert recorded[0]["requests"] == 1
    assert recorded[0]["successes"] == 0
    assert recorded[0]["failures"] == 1



def test_memory_bridge_observability_is_authenticated_and_never_touches_supabase(
    monkeypatch,
):
    configure(monkeypatch)
    called = {"database": 0, "summary": 0}

    def should_not_run():
        called["database"] += 1
        raise AssertionError("observability endpoint must not touch Supabase")

    class Observability:
        def memory_bridge_slo_snapshot(self):
            called["summary"] += 1
            return {
                "storage": "railway-redis-volume",
                "targets": {
                    "min_samples": 20,
                    "availability": 0.99,
                    "latency_ms": 3000.0,
                    "history_limit": 100,
                },
                "deployment": {
                    "status": "warming",
                    "samples": 8,
                    "successes": 8,
                    "failures": 0,
                    "availability": 1.0,
                    "ewma_latency_ms": 1461.6,
                },
                "runtime": {
                    "status": "warming",
                    "samples": 3,
                    "successes": 3,
                    "failures": 0,
                    "availability": 1.0,
                    "mean_latency_ms": 1428.7,
                    "periodic_rollups": 1,
                    "shutdown_rollups": 0,
                    "canary_rollups": 4,
                },
            }

    import orchestration.lieutenants.observability_lieutenant as obs_module

    monkeypatch.setattr(bridge, "_database", should_not_run)
    monkeypatch.setattr(
        obs_module,
        "OBSERVABILITY_LIEUTENANT",
        Observability(),
    )

    response = client().get(
        "/internal/shine-ai/memory/observability",
        headers={"X-Shine-Service-Token": "x" * 32},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "project-l"
    assert body["component"] == "memory-bridge-observability"
    assert body["version"] == "1.0"
    assert body["database_touched"] is False
    assert body["memory_content_included"] is False
    assert body["durable"]["storage"] == "railway-redis-volume"
    assert body["durable"]["deployment"]["samples"] == 8
    assert body["durable"]["runtime"]["samples"] == 3
    assert body["durable"]["runtime"]["canary_rollups"] == 4
    assert body["process_metrics"]["runtime_rollup"]["interval_seconds"] == 300.0
    assert called == {"database": 0, "summary": 1}

    raw = str(body).lower()
    for forbidden in (
        "diving bali",
        "secret memory",
        OWNER.lower(),
        "service-role-key",
    ):
        assert forbidden not in raw

    denied = client().get(
        "/internal/shine-ai/memory/observability",
        headers={"X-Shine-Service-Token": "wrong"},
    )
    assert denied.status_code == 401
    assert called == {"database": 0, "summary": 1}



def test_account_boundary_allows_internal_memory_service_auth_routes():
    server_source = (
        Path(__file__).resolve().parents[1] / "api" / "server.py"
    ).read_text()
    public_block = server_source.split("public_paths =", 1)[1].split(
        "path = request.url.path", 1
    )[0]

    for route in (
        "/internal/shine-ai/memory/retrieve",
        "/internal/shine-ai/memory/health",
        "/internal/shine-ai/memory/observability",
    ):
        assert route in public_block

    assert "if path not in public_paths" in server_source



def test_memory_retrieval_contract_manifest_matches_live_boundary():
    manifest = bridge.memory_retrieval_contract_manifest()

    assert manifest["query_contract_version"] == bridge._QUERY_CONTRACT_VERSION
    assert manifest["endpoint"] == "/internal/shine-ai/memory/retrieve"
    assert manifest["request"]["fields"] == list(
        bridge.MemoryRetrieveRequest.model_fields
    )
    assert manifest["response"]["record_fields"] == list(
        bridge.MemoryRecordResponse.model_fields
    )
    assert manifest["response"]["engine"] == bridge._RETRIEVAL_ENGINE
    assert manifest["response"]["version"] == bridge._RETRIEVAL_VERSION
    assert manifest["scope_policy"] == {
        app: sorted(scopes)
        for app, scopes in sorted(bridge._APP_SCOPE_POLICY.items())
    }
    assert manifest["semantics"] == {
        "read_only": True,
        "permission_scoped": True,
        "broad_recall_rejected": True,
        "legacy_global_search_used": False,
        "legacy_rpc_fallback_used": False,
    }


def test_memory_retrieval_contract_fingerprint_is_deterministic():
    first = bridge.memory_retrieval_contract_sha256()
    second = bridge.memory_retrieval_contract_sha256()

    assert first == second
    assert first == (
        "caf74ae7d02551b093a11699493b4eaa9185e9c0f3b813644af260d9c0d674ae"
    )



def test_memory_bridge_health_attests_nonce_bound_content(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    nonce = "shine-ai-health-nonce-0001"

    response = client().get(
        "/internal/shine-ai/memory/health",
        headers={
            "X-Shine-Service-Token": "x" * 32,
            "X-Shine-Health-Nonce": nonce,
        },
    )

    assert response.status_code == 200
    body = response.json()
    attestation = body.pop("attestation")
    assert attestation["version"] == 1
    assert attestation["algorithm"] == "HMAC-SHA-256"
    assert attestation["key_id"] == "health-test-v1"
    assert attestation["domain"] == bridge._HEALTH_ATTESTATION_DOMAIN
    assert attestation["nonce"] == nonce

    canonical = json.dumps(
        body,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    payload_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert attestation["payload_sha256"] == payload_sha256
    material = (
        bridge._HEALTH_ATTESTATION_DOMAIN
        + "\n"
        + nonce
        + "\n"
        + payload_sha256
    ).encode("utf-8")
    expected_signature = hmac.new(
        ("h" * 48).encode("utf-8"),
        material,
        hashlib.sha256,
    ).hexdigest()
    assert hmac.compare_digest(
        attestation["signature_sha256"],
        expected_signature,
    )
    assert "x" * 32 not in response.text


def test_memory_bridge_health_rejects_invalid_attestation_nonce(monkeypatch):
    configure(monkeypatch)

    response = client().get(
        "/internal/shine-ai/memory/health",
        headers={
            "X-Shine-Service-Token": "x" * 32,
            "X-Shine-Health-Nonce": "short",
        },
    )

    assert response.status_code == 422



def test_health_attestation_uses_dedicated_key_not_service_token(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    nonce = "shine-ai-health-key-separation-0001"

    response = client().get(
        "/internal/shine-ai/memory/health",
        headers={
            "X-Shine-Service-Token": "x" * 32,
            "X-Shine-Health-Nonce": nonce,
        },
    )

    assert response.status_code == 200
    body = response.json()
    attestation = body.pop("attestation")
    canonical = json.dumps(
        body,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    payload_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    material = (
        bridge._HEALTH_ATTESTATION_DOMAIN
        + "\n"
        + nonce
        + "\n"
        + payload_sha256
    ).encode("utf-8")
    request_token_signature = hmac.new(
        ("x" * 32).encode("utf-8"),
        material,
        hashlib.sha256,
    ).hexdigest()

    assert attestation["key_id"] == "health-test-v1"
    assert not hmac.compare_digest(
        attestation["signature_sha256"],
        request_token_signature,
    )


def test_health_attestation_requires_dedicated_key_when_nonce_present(
    monkeypatch,
):
    configure(monkeypatch)
    monkeypatch.delenv(
        "SHINE_AI_MEMORY_HEALTH_ATTESTATION_KEY",
        raising=False,
    )

    response = client().get(
        "/internal/shine-ai/memory/health",
        headers={
            "X-Shine-Service-Token": "x" * 32,
            "X-Shine-Health-Nonce": "shine-ai-health-missing-key-0001",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Project L health attestation key is unavailable."
    )



def test_health_attestation_keyring_selects_active_key(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv(
        "SHINE_AI_MEMORY_HEALTH_ATTESTATION_ACTIVE_KEY_ID",
        "health-b",
    )
    monkeypatch.setenv(
        "SHINE_AI_MEMORY_HEALTH_ATTESTATION_KEYRING_JSON",
        json.dumps({
            "health-a": "a" * 48,
            "health-b": "b" * 48,
        }),
    )

    key_id, key = bridge._configured_health_attestation_key()

    assert key_id == "health-b"
    assert key == "b" * 48


def test_health_attestation_keyring_fails_if_active_key_missing(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv(
        "SHINE_AI_MEMORY_HEALTH_ATTESTATION_ACTIVE_KEY_ID",
        "health-b",
    )
    monkeypatch.setenv(
        "SHINE_AI_MEMORY_HEALTH_ATTESTATION_KEYRING_JSON",
        json.dumps({"health-a": "a" * 48}),
    )

    with pytest.raises(Exception) as caught:
        bridge._configured_health_attestation_key()

    assert getattr(caught.value, "status_code", None) == 503
    assert "active health attestation key" in str(
        getattr(caught.value, "detail", "")
    ).lower()


def test_health_attestation_keyring_fails_closed_on_invalid_secret(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setenv(
        "SHINE_AI_MEMORY_HEALTH_ATTESTATION_ACTIVE_KEY_ID",
        "health-b",
    )
    monkeypatch.setenv(
        "SHINE_AI_MEMORY_HEALTH_ATTESTATION_KEYRING_JSON",
        json.dumps({"health-b": "short"}),
    )

    with pytest.raises(Exception) as caught:
        bridge._configured_health_attestation_key()

    assert getattr(caught.value, "status_code", None) == 503
    assert "keyring is invalid" in str(
        getattr(caught.value, "detail", "")
    ).lower()


def test_health_attestation_legacy_key_is_migration_fallback(monkeypatch):
    configure(monkeypatch)
    monkeypatch.delenv(
        "SHINE_AI_MEMORY_HEALTH_ATTESTATION_ACTIVE_KEY_ID",
        raising=False,
    )
    monkeypatch.delenv(
        "SHINE_AI_MEMORY_HEALTH_ATTESTATION_KEYRING_JSON",
        raising=False,
    )

    key_id, key = bridge._configured_health_attestation_key()

    assert key_id == "health-test-v1"
    assert key == "h" * 48
