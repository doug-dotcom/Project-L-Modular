from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.wellness_context as bridge

OWNER = "4ad046b3-06a5-4e62-a3ef-17a4f83dcdde"
TOKEN = "w" * 48


def client() -> TestClient:
    app = FastAPI()
    app.include_router(bridge.router)
    return TestClient(app)


def configure(monkeypatch):
    monkeypatch.setenv("WELLNESS_CONTEXT_SERVICE_TOKEN", TOKEN)
    monkeypatch.setenv("PROJECT_L_OWNER_ID", OWNER)


def owner_context():
    return {
        "status": "ok",
        "scope": {
            "ownerBound": True,
            "quarantineExcluded": True,
            "correctionsPreferred": True,
        },
        "_queryBinding": {
            "mode": "server-verified",
            "queryContractVersion": "2",
        },
        "matches": [
            {
                "id": "812",
                "domain": "health",
                "content": "Historical health context.",
                "provenance": {
                    "sourceTable": "memory_health",
                    "sourceId": "812",
                    "sourceRole": "user",
                    "ownerBound": True,
                },
            },
            {
                "id": "sport-1",
                "domain": "sport",
                "content": "Must not cross the health bridge.",
                "provenance": {
                    "sourceTable": "memory_sport",
                    "sourceId": "sport-1",
                    "sourceRole": "user",
                    "ownerBound": True,
                },
            },
            {
                "id": "unbound",
                "domain": "health",
                "content": "Unbound health memory.",
                "provenance": {
                    "sourceTable": "memory_health",
                    "sourceId": "unbound",
                    "sourceRole": "assistant",
                    "ownerBound": False,
                },
            },
        ],
    }


def payload(**overrides):
    data = {
        "request_contract": "shine-wellness/project-l-context-only-v1",
        "purpose": "wellness-longitudinal-context",
        "user_id": OWNER,
        "query": "What changed around my sleep?",
        "canonical_record_ids": ["wellness-record-1"],
        "permission_decision_id": "permission-1",
        "limit": 4,
    }
    data.update(overrides)
    return data


def test_context_is_owner_bound_health_only_and_non_authoritative(monkeypatch):
    configure(monkeypatch)
    seen = {}

    def retrieve(owner_id, query, limit):
        seen.update(owner_id=owner_id, query=query, limit=limit)
        return owner_context()

    monkeypatch.setattr(bridge, "_owner_context", retrieve)

    response = client().post(
        "/internal/wellness/context",
        headers={"X-Wellness-Service-Token": TOKEN},
        json=payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["contract"] == "shine-wellness/project-l-context-only-v1"
    assert body["authority"] == "context_only"
    assert body["health_truth_authority"] is False
    assert body["read_only"] is True
    assert body["canonical_record_ids"] == ["wellness-record-1"]
    assert body["permission_decision_id"] == "permission-1"
    assert [record["id"] for record in body["records"]] == [
        "memory_health:812"
    ]
    assert body["records"][0]["authority"] == "context_only"
    assert body["records"][0]["fact_authority"] == "none"
    assert body["records"][0]["owner_bound"] is True
    assert body["receipt"]["writes_performed"] is False
    assert body["receipt"]["broad_recall_allowed"] is False
    assert seen["owner_id"] == OWNER
    assert seen["query"].startswith("health ")
    assert seen["limit"] == 6


def test_invalid_service_token_is_rejected_before_memory_query(monkeypatch):
    configure(monkeypatch)
    called = {"value": False}

    def should_not_run(*args, **kwargs):
        called["value"] = True
        raise AssertionError("retrieval must not run")

    monkeypatch.setattr(bridge, "_owner_context", should_not_run)

    response = client().post(
        "/internal/wellness/context",
        headers={"X-Wellness-Service-Token": "wrong"},
        json=payload(),
    )

    assert response.status_code == 401
    assert called["value"] is False


def test_owner_mismatch_is_rejected_before_memory_query(monkeypatch):
    configure(monkeypatch)
    called = {"value": False}
    monkeypatch.setattr(
        bridge,
        "_owner_context",
        lambda *args, **kwargs: called.update(value=True),
    )

    response = client().post(
        "/internal/wellness/context",
        headers={"X-Wellness-Service-Token": TOKEN},
        json=payload(user_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
    )

    assert response.status_code == 403
    assert called["value"] is False


def test_broad_recall_is_rejected_before_memory_query(monkeypatch):
    configure(monkeypatch)
    called = {"value": False}
    monkeypatch.setattr(
        bridge,
        "_owner_context",
        lambda *args, **kwargs: called.update(value=True),
    )

    response = client().post(
        "/internal/wellness/context",
        headers={"X-Wellness-Service-Token": TOKEN},
        json=payload(query="Deep recall everything you know about me"),
    )

    assert response.status_code == 422
    assert called["value"] is False


def test_request_requires_canonical_and_permission_references(monkeypatch):
    configure(monkeypatch)

    missing_permission = payload()
    missing_permission.pop("permission_decision_id")
    denied = client().post(
        "/internal/wellness/context",
        headers={"X-Wellness-Service-Token": TOKEN},
        json=missing_permission,
    )
    assert denied.status_code == 422

    invalid_record = client().post(
        "/internal/wellness/context",
        headers={"X-Wellness-Service-Token": TOKEN},
        json=payload(canonical_record_ids=["bad record with spaces"]),
    )
    assert invalid_record.status_code == 422


def test_empty_health_context_stays_non_authoritative(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(
        bridge,
        "_owner_context",
        lambda *args, **kwargs: {
            "status": "ok",
            "scope": {"ownerBound": True},
            "_queryBinding": {"mode": "server-verified"},
            "matches": [],
        },
    )

    response = client().post(
        "/internal/wellness/context",
        headers={"X-Wellness-Service-Token": TOKEN},
        json=payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["records"] == []
    assert body["authority"] == "context_only"
    assert body["health_truth_authority"] is False
