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
