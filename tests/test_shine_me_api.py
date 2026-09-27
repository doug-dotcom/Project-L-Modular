"""HTTP boundary checks for Shine-Me's owner-only preview routes."""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.shine_me import routes


def make_client(monkeypatch, owner="owner-a", *, approved=True):
    monkeypatch.setenv("PROJECT_L_OWNER_ID", owner)
    calls = []

    def retrieve(query):
        calls.append("retrieve")
        return {"evidence": [{
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

    app.include_router(routes(retrieve, cognize))
    return TestClient(app), calls


def test_owner_can_ask_for_gated_memory(monkeypatch):
    client, calls = make_client(monkeypatch)
    response = client.post(
        "/shine-me/ask", json={"query": "What do I prefer?"},
        headers={"x-test-verified-user": "owner-a"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "quoted_user_memory"
    assert "I like context first" in response.json()["reply"]
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


def test_missing_owner_configuration_fails_closed(monkeypatch):
    client, calls = make_client(monkeypatch)
    monkeypatch.delenv("PROJECT_L_OWNER_ID")
    response = client.post(
        "/shine-me/ask", json={"query": "my memory"},
        headers={"x-test-verified-user": "owner-a"},
    )
    assert response.status_code == 503
    assert calls == []
