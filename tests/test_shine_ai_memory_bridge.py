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
    monkeypatch.setattr(bridge, "_bound_owner", lambda: OWNER)
    bridge._db_client = None


def owner_context():
    return {
        "status": "ok",
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
    assert body["receipt"]["unavailable_scopes"] == ["episodic"]
    assert body["receipt"]["read_only"] is True
    assert body["receipt"]["bounded"] is True


def test_invalid_service_token_is_rejected_before_owner_resolution(monkeypatch):
    configure(monkeypatch)
    called = {"owner": False, "query": False}

    def should_not_bind():
        called["owner"] = True
        return OWNER

    def should_not_run(owner_id, query, limit):
        called["query"] = True
        return owner_context()

    monkeypatch.setattr(bridge, "_bound_owner", should_not_bind)
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
    assert called == {"owner": False, "query": False}


def test_server_owned_binding_ignores_caller_owner_and_keeps_scope_boundary(monkeypatch):
    configure(monkeypatch)
    seen = {"owner": None}

    def scoped(owner_id, query, limit):
        seen["owner"] = owner_id
        return owner_context()

    monkeypatch.setattr(bridge, "_owner_context", scoped)

    redirected = client().post(
        "/internal/shine-ai/memory/retrieve",
        headers={"X-Shine-Service-Token": "x" * 32},
        json={
            "app": "shine-dive",
            "user_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "query": "Dive history",
            "scopes": ["sport"],
        },
    )
    assert redirected.status_code == 200
    assert seen["owner"] == OWNER
    redirected_body = redirected.json()
    assert redirected_body["receipt"]["owner_binding_source"] == "project_l_account"
    assert redirected_body["receipt"]["caller_user_id_authoritative"] is False

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
    assert len(terms) <= 24
