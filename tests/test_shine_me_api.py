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

    def list_reviews(owner_id):
        calls.append(("list", owner_id))
        return type("Reviews", (), {"data": [{
            "id": "review-1", "owner_id": owner_id, "question": "What do I prefer?",
            "source": "memory_general:1", "provenance": "user_statement",
            "issue_kind": "wrong", "proposed_correction": "Context first.",
            "status": "pending_review", "created_at": "2026-09-27T00:00:00Z",
        }]})()

    state_store = {}

    def load_state(owner_id):
        calls.append(("state_load", owner_id))
        row = state_store.get(owner_id)
        return type("State", (), {"data": [dict(row)] if row else []})()

    def insert_state(row):
        calls.append(("state_insert", row))
        if row["owner_id"] in state_store:
            raise RuntimeError("duplicate")
        state_store[row["owner_id"]] = dict(row)
        return type("State", (), {"data": [dict(row)]})()

    def update_state(owner_id, expected_revision, row):
        calls.append(("state_update", owner_id, expected_revision, row))
        current = state_store.get(owner_id)
        if not current or current["revision"] != expected_revision:
            return type("State", (), {"data": []})()
        state_store[owner_id] = dict(row)
        return type("State", (), {"data": [dict(row)]})()

    app.include_router(routes(
        retrieve, cognize, lambda receipt: {"status": freshness},
        save, list_reviews, load_state, insert_state, update_state,
    ))
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


def test_owner_lists_only_own_corrections_without_retrieval(monkeypatch):
    client, calls = make_client(monkeypatch)
    assert client.get("/shine-me/corrections",
                      headers={"x-test-verified-user": "other"}).status_code == 403
    assert calls == []
    response = client.get("/shine-me/corrections",
                          headers={"x-test-verified-user": "owner-a"})
    assert response.status_code == 200
    assert response.json()["items"][0]["status"] == "pending_review"
    assert "owner_id" not in response.json()["items"][0]
    assert calls == [("list", "owner-a")]


def test_correction_list_rejects_cross_owner_storage_result(monkeypatch):
    import os
    from fastapi import FastAPI

    client, calls = make_client(monkeypatch)
    # Replace the route's storage callback by building an isolated router.
    app = FastAPI()

    @app.middleware("http")
    async def verified(request, call_next):
        request.state.account = {"user_id": "owner-a"}
        return await call_next(request)

    def wrong_owner(_):
        return type("Reviews", (), {"data": [{"owner_id": "other"}]})()

    app.include_router(routes(lambda _: {}, lambda *_: {}, lambda _: {},
                              list_corrections=wrong_owner))
    response = TestClient(app).get("/shine-me/corrections")
    assert response.status_code == 503


def test_owner_state_sync_is_owner_bound_and_memory_separate(monkeypatch):
    client, calls = make_client(monkeypatch)
    headers = {"x-test-verified-user": "owner-a"}

    response = client.get("/shine-me/state", headers=headers)
    assert response.status_code == 200
    assert response.json() == {
        "status": "empty", "state": None, "revision": 0, "updated_at": None,
    }
    assert calls == [("state_load", "owner-a")]

    state = {
        "mood": 4,
        "moodNote": "Steady",
        "goals": [{"text": "Walk", "done": False, "completedOn": None}],
        "routines": [],
        "history": {},
        "journal": [],
        "lastDay": "2026-10-01",
    }
    response = client.put(
        "/shine-me/state",
        json={"state": state, "expected_revision": 0},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["revision"] == 1
    assert "retrieve" not in calls and "cognize" not in calls

    response = client.get("/shine-me/state", headers=headers)
    assert response.status_code == 200
    assert response.json()["state"]["mood"] == 4
    assert response.json()["revision"] == 1


def test_owner_state_sync_rejects_stale_revision(monkeypatch):
    client, _ = make_client(monkeypatch)
    headers = {"x-test-verified-user": "owner-a"}
    state = {
        "mood": None, "moodNote": "", "goals": [], "routines": [],
        "history": {}, "journal": [], "lastDay": "2026-10-01",
    }
    first = client.put(
        "/shine-me/state",
        json={"state": state, "expected_revision": 0},
        headers=headers,
    )
    assert first.status_code == 200
    assert first.json()["revision"] == 1

    state["mood"] = 3
    second = client.put(
        "/shine-me/state",
        json={"state": state, "expected_revision": 1},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["revision"] == 2

    stale = client.put(
        "/shine-me/state",
        json={"state": state, "expected_revision": 1},
        headers=headers,
    )
    assert stale.status_code == 409


def test_owner_state_sync_rejects_other_account_and_unknown_fields(monkeypatch):
    client, calls = make_client(monkeypatch)
    state = {
        "mood": None, "moodNote": "", "goals": [], "routines": [],
        "history": {}, "journal": [], "lastDay": "2026-10-01",
    }
    assert client.get(
        "/shine-me/state", headers={"x-test-verified-user": "other"},
    ).status_code == 403
    assert calls == []

    state["owner_id"] = "owner-a"
    response = client.put(
        "/shine-me/state",
        json={"state": state, "expected_revision": 0},
        headers={"x-test-verified-user": "owner-a"},
    )
    assert response.status_code == 400
