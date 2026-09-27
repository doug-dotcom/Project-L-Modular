"""HTTP boundary checks for Shine-Me's owner-only preview routes."""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.shine_me import routes


def make_client(monkeypatch, owner="owner-a", *, approved=True, freshness="unchanged"):
    monkeypatch.setenv("PROJECT_L_OWNER_ID", owner)
    monkeypatch.setenv("L_MEMORY_OWNER_ID", owner)
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-only-key")
    calls = []

    def retrieve(query):
        calls.append("retrieve")
        return {"recall_plan": {"status": "checked"},
                "temporal_memory": {"status": "checked", "user_id": owner},
                "evidence": [{
            "source": "memory_general:1", "role": "user",
            "quote_source": "I like context first.",
        }]}

    def cognize(query, packet):
        calls.append("cognize")
        return {key: {
            "active": True,
            "decision": "surface" if approved else "silent",
            "surface_allowed": approved,
            "source": "memory_general:1" if approved else None,
        } for key in (
            "memory_temporal_drift", "memory_privacy", "memory_identity",
            "memory_emotional_salience", "memory_causal_attribution",
        )}

    app = FastAPI()

    @app.middleware("http")
    async def account_stub(request: Request, call_next):
        # Test-only stand-in for Project L's verified account middleware.
        user_id = request.headers.get("x-test-verified-user")
        if user_id:
            request.state.account = {"user_id": user_id}
        return await call_next(request)

    def save(row):
        calls.append(("save", row))
        return type("Saved", (), {"data": [{"id": "review-1"}]})()

    app.include_router(routes(retrieve, cognize, lambda receipt: {"status": freshness}, save))
    return TestClient(app), calls


def test_owner_binding_check_never_retrieves_memory(monkeypatch):
    client, calls = make_client(monkeypatch)
    response = client.get(
        "/shine-me/binding", headers={"x-test-verified-user": "owner-a"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "binding_ready", "reason": "owner_ids_match"}
    assert calls == []
    monkeypatch.setenv("L_MEMORY_OWNER_ID", "other")
    response = client.get(
        "/shine-me/binding", headers={"x-test-verified-user": "owner-a"},
    )
    assert response.json()["status"] == "unavailable"
    assert calls == []
    response = client.get(
        "/shine-me/binding", headers={"x-test-verified-user": "other"},
    )
    assert response.status_code == 403
    assert calls == []


def test_owner_can_ask_for_gated_memory(monkeypatch):
    client, calls = make_client(monkeypatch)
    response = client.post(
        "/shine-me/ask", json={"query": "What do I prefer?"},
        headers={"x-test-verified-user": "owner-a"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "quoted_user_memory"
    assert "I like context first" in response.json()["reply"]
    assert response.json()["why"]["source"] == "memory_general:1"
    assert calls == ["retrieve", "cognize"]


def test_missing_or_other_account_does_not_retrieve(monkeypatch):
    client, calls = make_client(monkeypatch)
    for headers in ({}, {"x-test-verified-user": "other"}):
        response = client.post(
            "/shine-me/context", json={"query": "my memory"}, headers=headers,
        )
        assert response.status_code == 403
    assert calls == []


def test_body_user_id_cannot_override_verified_account(monkeypatch):
    client, calls = make_client(monkeypatch)
    response = client.post(
        "/shine-me/ask",
        json={"query": "my memory", "user_id": "owner-a"},
        headers={"x-test-verified-user": "other"},
    )
    assert response.status_code == 403
    assert calls == []


def test_veto_produces_honest_empty_answer(monkeypatch):
    client, calls = make_client(monkeypatch, approved=False)
    response = client.post(
        "/shine-me/ask", json={"query": "my memory"},
        headers={"x-test-verified-user": "owner-a"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "no_approved_evidence"
    assert response.json()["evidence"] == []
    assert calls == ["retrieve", "cognize"]


def test_memory_namespace_mismatch_fails_before_retrieval(monkeypatch):
    client, calls = make_client(monkeypatch)
    monkeypatch.setenv("L_MEMORY_OWNER_ID", "other")
    response = client.post(
        "/shine-me/ask", json={"query": "my memory"},
        headers={"x-test-verified-user": "owner-a"},
    )
    assert response.status_code == 503
    assert calls == []


def test_changed_timeline_never_returns_a_memory(monkeypatch):
    client, calls = make_client(monkeypatch, freshness="changed")
    response = client.post(
        "/shine-me/ask", json={"query": "my memory"},
        headers={"x-test-verified-user": "owner-a"},
    )
    assert response.status_code == 503
    assert "reply" not in response.json()
    assert calls == ["retrieve", "cognize"]


def test_missing_owner_configuration_fails_closed(monkeypatch):
    client, calls = make_client(monkeypatch)
    monkeypatch.delenv("PROJECT_L_OWNER_ID")
    response = client.post(
        "/shine-me/ask", json={"query": "my memory"},
        headers={"x-test-verified-user": "owner-a"},
    )
    assert response.status_code == 503
    assert calls == []


def test_real_server_account_middleware_guards_shine_me(monkeypatch):
    from fastapi import HTTPException
    import api.server as server

    monkeypatch.setenv("PROJECT_L_OWNER_ID", "owner-a")
    monkeypatch.setenv("L_MEMORY_OWNER_ID", "owner-a")

    def verified_account(client, authorization):
        if authorization == "Bearer owner":
            return {"user_id": "owner-a"}
        if authorization == "Bearer other":
            return {"user_id": "other"}
        raise HTTPException(401, "Sign in required")

    monkeypatch.setattr(server, "require_account", verified_account)
    client = TestClient(server.app)
    assert client.get("/shine-me/binding").status_code == 401
    assert client.get(
        "/shine-me/binding", headers={"Authorization": "Bearer other"}
    ).status_code == 403
    response = client.get(
        "/shine-me/binding", headers={"Authorization": "Bearer owner"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "binding_ready", "reason": "owner_ids_match"}
    assert client.post(
        "/shine-me/ask", json={"query": "personal memory"},
        headers={"Authorization": "Bearer other"},
    ).status_code == 403


def test_owner_submits_source_checked_review_without_memory_write(monkeypatch):
    client, calls = make_client(monkeypatch)
    response = client.post("/shine-me/corrections", json={
        "query": "What do I prefer?", "expected_source": "memory_general:1",
        "issue_kind": "incomplete", "proposed_correction": " Context first, then detail. ",
    }, headers={"x-test-verified-user": "owner-a"})
    assert response.status_code == 200
    assert response.json() == {"status": "pending_review", "id": "review-1"}
    assert calls[:2] == ["retrieve", "cognize"]
    saved = calls[2][1]
    assert saved["owner_id"] == "owner-a"
    assert saved["source"] == "memory_general:1"
    assert saved["proposed_correction"] == "Context first, then detail."
    assert saved["original_reply"].startswith("I found this in something you said")


def test_correction_rejects_other_account_and_changed_source(monkeypatch):
    client, calls = make_client(monkeypatch)
    payload = {"query": "What do I prefer?", "expected_source": "memory_general:1",
               "issue_kind": "wrong", "proposed_correction": "Context first."}
    assert client.post("/shine-me/corrections", json=payload,
                       headers={"x-test-verified-user": "other"}).status_code == 403
    assert calls == []
    payload["expected_source"] = "memory_general:another"
    response = client.post("/shine-me/corrections", json=payload,
                           headers={"x-test-verified-user": "owner-a"})
    assert response.status_code == 409
    assert calls == ["retrieve", "cognize"]


def test_correction_requires_server_secret_and_approved_evidence(monkeypatch):
    client, calls = make_client(monkeypatch)
    payload = {"query": "What do I prefer?", "expected_source": "memory_general:1",
               "issue_kind": "wrong", "proposed_correction": "Context first."}
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY")
    assert client.post("/shine-me/corrections", json=payload,
                       headers={"x-test-verified-user": "owner-a"}).status_code == 503
    assert calls == ["retrieve", "cognize"]
    client, calls = make_client(monkeypatch, approved=False)
    assert client.post("/shine-me/corrections", json=payload,
                       headers={"x-test-verified-user": "owner-a"}).status_code == 409
    assert calls == ["retrieve", "cognize"]
