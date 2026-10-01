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
    conflict_store = {}
    conflict_counter = {"value": 0}

    def load_state(owner_id):
        calls.append(("state_load", owner_id))
        row = state_store.get(owner_id)
        return type("State", (), {"data": [dict(row)] if row else []})()

    def apply_state(owner_id, expected_revision, state):
        calls.append(("state_apply", owner_id, expected_revision, dict(state)))
        current = state_store.get(owner_id)
        if expected_revision == 0:
            if current is not None:
                raise RuntimeError("REVISION_CONFLICT")
            next_revision = 1
        else:
            if not current or current["revision"] != expected_revision:
                raise RuntimeError("REVISION_CONFLICT")
            next_revision = expected_revision + 1
        row = {
            "owner_id": owner_id,
            "state": dict(state),
            "revision": next_revision,
            "updated_at": f"2026-10-01T00:00:0{min(next_revision, 9)}Z",
        }
        state_store[owner_id] = row
        return type("State", (), {"data": [dict(row)]})()

    def record_conflict(owner_id, local_revision):
        calls.append(("conflict_detect", owner_id, local_revision))
        current = state_store.get(owner_id)
        if not current or current["revision"] == local_revision:
            raise RuntimeError("NO_ACTIVE_REVISION_CONFLICT")
        remote_revision = current["revision"]
        for conflict_id, item in conflict_store.items():
            if (
                item["owner_id"] == owner_id
                and item["local_revision"] == local_revision
                and item["remote_revision"] == remote_revision
                and not item.get("resolved")
            ):
                recent = len(conflict_store)
                return type("Conflict", (), {"data": [{
                    "conflict_id": conflict_id,
                    "remote_revision": remote_revision,
                    "recent_conflicts_24h": recent,
                    "recurring": recent >= 3,
                }]})()
        conflict_counter["value"] += 1
        conflict_id = f"00000000-0000-4000-8000-{conflict_counter['value']:012d}"
        conflict_store[conflict_id] = {
            "owner_id": owner_id,
            "local_revision": local_revision,
            "remote_revision": remote_revision,
            "resolved": False,
        }
        recent = len(conflict_store)
        return type("Conflict", (), {"data": [{
            "conflict_id": conflict_id,
            "remote_revision": remote_revision,
            "recent_conflicts_24h": recent,
            "recurring": recent >= 3,
        }]})()

    def resolve_conflict(owner_id, conflict_id, resolution, resolved_revision):
        calls.append((
            "conflict_resolve", owner_id, conflict_id, resolution, resolved_revision,
        ))
        item = conflict_store.get(conflict_id)
        if not item or item["owner_id"] != owner_id:
            raise RuntimeError("CONFLICT_NOT_FOUND")
        if item.get("resolved"):
            if (
                item["resolution"] == resolution
                and item["resolved_revision"] == resolved_revision
            ):
                status = "already_resolved"
            else:
                raise RuntimeError("CONFLICT_ALREADY_RESOLVED")
        else:
            if resolution == "account_copy" and resolved_revision != item["remote_revision"]:
                raise RuntimeError("ACCOUNT_RESOLUTION_REVISION_MISMATCH")
            if resolution == "device_copy" and resolved_revision <= item["remote_revision"]:
                raise RuntimeError("DEVICE_RESOLUTION_REVISION_MISMATCH")
            item["resolved"] = True
            item["resolution"] = resolution
            item["resolved_revision"] = resolved_revision
            status = "resolved"
        return type("ConflictResolution", (), {"data": [{
            "status": status,
            "resolution": resolution,
            "resolved_revision": resolved_revision,
        }]})()

    def conflict_health(owner_id):
        calls.append(("conflict_health", owner_id))
        items = [
            item for item in conflict_store.values()
            if item["owner_id"] == owner_id
        ]
        detections = len(items)
        resolutions = sum(1 for item in items if item.get("resolved"))
        unresolved = detections - resolutions
        recurring = detections >= 3
        persistent = detections >= 6 or unresolved >= 2
        status = (
            "persistent" if persistent else
            "recurring" if recurring else
            "isolated" if detections or unresolved else
            "stable"
        )
        return type("ConflictHealth", (), {"data": [{
            "health_status": status,
            "detections_24h": detections,
            "resolutions_24h": resolutions,
            "unresolved_conflicts": unresolved,
            "oldest_unresolved_minutes": 0,
            "last_conflict_at": None,
            "recurring": recurring,
            "persistent": persistent,
        }]})()

    app.include_router(routes(
        retrieve, cognize, lambda receipt: {"status": freshness},
        save, list_reviews, load_state, apply_state,
        record_conflict, resolve_conflict, conflict_health,
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
    assert calls[-1][0] == "state_apply"
    assert calls[-1][1:3] == ("owner-a", 0)
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
    conflict = stale.json()["detail"]
    assert conflict["conflict_observability"] == "recorded"
    assert conflict["remote_revision"] == 2
    assert conflict["recent_conflicts_24h"] == 1
    assert conflict["recurring"] is False
    assert conflict["conflict_id"]

    remote = client.get("/shine-me/state", headers=headers)
    assert remote.status_code == 200
    assert remote.json()["revision"] == 2
    assert remote.json()["state"]["mood"] == 3

    # This models the browser's explicit "Keep this device" reconciliation:
    # rebase the preserved local copy onto the freshly loaded account revision,
    # then retry with the opaque conflict id. Resolution is recorded only after
    # the atomic state write succeeds.
    state["mood"] = 4
    reconciled = client.put(
        "/shine-me/state",
        json={
            "state": state,
            "expected_revision": remote.json()["revision"],
            "conflict_id": conflict["conflict_id"],
        },
        headers=headers,
    )
    assert reconciled.status_code == 200
    assert reconciled.json()["revision"] == 3
    assert reconciled.json()["conflict_resolution_recorded"] is True


def test_owner_state_conflict_detect_and_account_resolution_are_content_free(monkeypatch):
    client, calls = make_client(monkeypatch)
    headers = {"x-test-verified-user": "owner-a"}
    state = {
        "mood": 2, "moodNote": "private words", "goals": [], "routines": [],
        "history": {}, "journal": [], "lastDay": "2026-10-01",
    }
    assert client.put(
        "/shine-me/state",
        json={"state": state, "expected_revision": 0},
        headers=headers,
    ).status_code == 200

    detection = client.post(
        "/shine-me/state/conflicts/detect",
        json={"local_revision": 0},
        headers=headers,
    )
    assert detection.status_code == 200
    receipt = detection.json()
    assert receipt["status"] == "recorded"
    assert receipt["remote_revision"] == 1
    assert receipt["recent_conflicts_24h"] == 1
    assert receipt["recurring"] is False
    assert "private words" not in str(receipt)

    resolution = client.post(
        "/shine-me/state/conflicts/resolve",
        json={
            "conflict_id": receipt["conflict_id"],
            "resolution": "account_copy",
            "resolved_revision": 1,
        },
        headers=headers,
    )
    assert resolution.status_code == 200
    assert resolution.json() == {
        "status": "resolved",
        "resolution": "account_copy",
        "resolved_revision": 1,
    }
    conflict_calls = [call for call in calls if isinstance(call, tuple) and call[0].startswith("conflict_")]
    assert conflict_calls[0] == ("conflict_detect", "owner-a", 0)
    assert conflict_calls[1][0:2] == ("conflict_resolve", "owner-a")
    assert "private words" not in str(conflict_calls)



def test_owner_state_conflict_health_moves_from_stable_to_recurring(monkeypatch):
    client, calls = make_client(monkeypatch)
    headers = {"x-test-verified-user": "owner-a"}
    state = {
        "mood": None, "moodNote": "", "goals": [], "routines": [],
        "history": {}, "journal": [], "lastDay": "2026-10-01",
    }

    stable = client.get("/shine-me/state/conflicts/health", headers=headers)
    assert stable.status_code == 200
    assert stable.json() == {
        "status": "stable",
        "detections_24h": 0,
        "resolutions_24h": 0,
        "unresolved_conflicts": 0,
        "oldest_unresolved_minutes": 0,
        "last_conflict_at": None,
        "recurring": False,
        "persistent": False,
    }

    for expected_revision in range(3):
        if expected_revision == 0:
            assert client.put(
                "/shine-me/state",
                json={"state": state, "expected_revision": 0},
                headers=headers,
            ).status_code == 200
        else:
            assert client.put(
                "/shine-me/state",
                json={"state": state, "expected_revision": expected_revision},
                headers=headers,
            ).status_code == 200

        detected = client.post(
            "/shine-me/state/conflicts/detect",
            json={"local_revision": expected_revision},
            headers=headers,
        )
        assert detected.status_code == 200
        receipt = detected.json()

        resolved = client.post(
            "/shine-me/state/conflicts/resolve",
            json={
                "conflict_id": receipt["conflict_id"],
                "resolution": "account_copy",
                "resolved_revision": expected_revision + 1,
            },
            headers=headers,
        )
        assert resolved.status_code == 200

    recurring = client.get("/shine-me/state/conflicts/health", headers=headers)
    assert recurring.status_code == 200
    assert recurring.json()["status"] == "recurring"
    assert recurring.json()["detections_24h"] == 3
    assert recurring.json()["resolutions_24h"] == 3
    assert recurring.json()["unresolved_conflicts"] == 0
    assert recurring.json()["recurring"] is True
    assert recurring.json()["persistent"] is False
    assert "state" not in recurring.json()
    assert "journal" not in recurring.json()
    assert ("conflict_health", "owner-a") in calls


def test_owner_state_conflict_health_is_owner_bound(monkeypatch):
    client, calls = make_client(monkeypatch)
    response = client.get(
        "/shine-me/state/conflicts/health",
        headers={"x-test-verified-user": "other"},
    )
    assert response.status_code == 403
    assert not any(
        isinstance(call, tuple) and call[0] == "conflict_health"
        for call in calls
    )


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


def test_owner_state_sync_accepts_bounded_daily_checkin(monkeypatch):
    client, _ = make_client(monkeypatch)
    state = {
        "mood": 3,
        "moodNote": "A note",
        "goals": [],
        "routines": [],
        "history": {},
        "journal": [],
        "dailyCheckins": {
            "2026-10-01": {
                "mood": 3,
                "feeling1": "calm",
                "feeling2": "hopeful",
                "score": 7.4,
                "sleep": 6.2,
                "gratitude": "A good morning",
                "challenge": "Admin",
                "intention": "Stay steady",
                "note": "Keep it simple",
                "updatedAt": "2026-10-01T08:00:00+10:00",
            }
        },
        "lastDay": "2026-10-01",
    }
    response = client.put(
        "/shine-me/state",
        json={"state": state, "expected_revision": 0},
        headers={"x-test-verified-user": "owner-a"},
    )
    assert response.status_code == 200

    loaded = client.get(
        "/shine-me/state", headers={"x-test-verified-user": "owner-a"},
    )
    assert loaded.status_code == 200
    checkin = loaded.json()["state"]["dailyCheckins"]["2026-10-01"]
    assert checkin["feeling1"] == "calm"
    assert checkin["score"] == 7.4
    assert checkin["sleep"] == 6.2


def test_owner_state_sync_rejects_invalid_daily_checkin_score(monkeypatch):
    client, _ = make_client(monkeypatch)
    state = {
        "mood": None,
        "moodNote": "",
        "goals": [],
        "routines": [],
        "history": {},
        "journal": [],
        "dailyCheckins": {
            "2026-10-01": {
                "mood": 2,
                "feeling1": "okay",
                "feeling2": "",
                "score": 11,
                "sleep": 5,
                "gratitude": "",
                "challenge": "",
                "intention": "",
                "note": "",
                "updatedAt": "2026-10-01T08:00:00+10:00",
            }
        },
        "lastDay": "2026-10-01",
    }
    response = client.put(
        "/shine-me/state",
        json={"state": state, "expected_revision": 0},
        headers={"x-test-verified-user": "owner-a"},
    )
    assert response.status_code == 400
