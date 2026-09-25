from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.shine_ai_memory as bridge


def client() -> TestClient:
    app = FastAPI()
    app.include_router(bridge.router)
    return TestClient(app)


def configure(monkeypatch):
    monkeypatch.setenv("SHINE_AI_MEMORY_TOKEN", "x" * 32)
    monkeypatch.setenv("PROJECT_L_OWNER_ID", "owner-1")


def packet():
    return {
        "engine": "rhee",
        "version": "v5.0",
        "recall_active": True,
        "recall_plan": {"status": "checked"},
        "evidence": [
            {
                "source": "episodic_memories:12",
                "quote_source": "Bali diving qualifications and dive history.",
                "role": "user",
            },
            {
                "source": "memory_sport:5507",
                "quote_source": "Diving training memory.",
                "role": "user",
            },
            {
                "source": "memory_general:abc",
                "quote_source": "General Shine Dive memory.",
                "role": "unknown",
            },
            {
                "source": "memory_recovery:5391",
                "quote_source": "Recovery information must not cross this scope boundary.",
                "role": "user",
            },
            {
                "source": "raw_catchall:5685",
                "quote_source": "Raw conversation is not exposed by the first bridge policy.",
                "role": "user",
            },
        ],
    }


def test_retrieval_is_service_authenticated_scoped_and_bounded(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(bridge, "build_rhee_packet", lambda query: packet())

    response = client().post(
        "/internal/shine-ai/memory/retrieve",
        headers={"X-Shine-Service-Token": "x" * 32},
        json={
            "app": "shine-dive",
            "user_id": "owner-1",
            "query": "What diving qualifications have I completed?",
            "scopes": ["episodic", "sport", "general"],
            "limit": 2,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "project-l"
    assert body["engine"] == "rhee"
    assert len(body["records"]) == 2
    assert body["records"][0]["id"] == "episodic_memories:12"
    assert body["records"][0]["priority"] == "high"
    assert all("recovery" not in record["text"].lower() for record in body["records"])
    assert body["receipt"]["read_only"] is True
    assert body["receipt"]["bounded"] is True


def test_invalid_service_token_is_rejected_before_recall(monkeypatch):
    configure(monkeypatch)
    called = {"value": False}

    def should_not_run(query):
        called["value"] = True
        return packet()

    monkeypatch.setattr(bridge, "build_rhee_packet", should_not_run)

    response = client().post(
        "/internal/shine-ai/memory/retrieve",
        headers={"X-Shine-Service-Token": "wrong"},
        json={
            "app": "shine-dive",
            "user_id": "owner-1",
            "query": "Dive history",
            "scopes": ["episodic"],
        },
    )

    assert response.status_code == 401
    assert called["value"] is False


def test_owner_and_scope_boundaries_are_enforced(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(bridge, "build_rhee_packet", lambda query: packet())

    wrong_owner = client().post(
        "/internal/shine-ai/memory/retrieve",
        headers={"X-Shine-Service-Token": "test-service-token"},
        json={
            "app": "shine-dive",
            "user_id": "someone-else",
            "query": "Dive history",
            "scopes": ["episodic"],
        },
    )
    assert wrong_owner.status_code == 403

    forbidden_scope = client().post(
        "/internal/shine-ai/memory/retrieve",
        headers={"X-Shine-Service-Token": "test-service-token"},
        json={
            "app": "shine-dive",
            "user_id": "owner-1",
            "query": "Health history",
            "scopes": ["health"],
        },
    )
    assert forbidden_scope.status_code == 403


def test_broad_recall_is_rejected(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(bridge, "build_rhee_packet", lambda query: packet())

    response = client().post(
        "/internal/shine-ai/memory/retrieve",
        headers={"X-Shine-Service-Token": "test-service-token"},
        json={
            "app": "shine-dive",
            "user_id": "owner-1",
            "query": "Deep recall everything you know about me",
            "scopes": ["episodic"],
        },
    )

    assert response.status_code == 422
