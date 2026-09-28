import hashlib
import hmac
import json

from services import shine_runtime_service as runtime


def test_shine_ai_signature_matches_keyring_contract(monkeypatch):
    monkeypatch.setenv("SHINE_AI_APP_ID", "shine-me")
    monkeypatch.setenv("SHINE_AI_APP_KEY_ID", "runtime-1")
    monkeypatch.setenv("SHINE_AI_APP_SECRET", "s" * 48)
    body = json.dumps({"app": "shine-me", "task": "route"}).encode()

    headers = runtime._shine_ai_headers(body, now=1_800_000_000, nonce="n" * 16)

    signed = b"\n".join([
        b"shine-me",
        b"runtime-1",
        b"1800000000",
        b"nnnnnnnnnnnnnnnn",
        b"POST",
        b"/v1/respond",
        body,
    ])
    expected = hmac.new(b"s" * 48, signed, hashlib.sha256).hexdigest()
    assert headers["X-Shine-Signature"] == expected
    assert headers["X-Shine-Key-Id"] == "runtime-1"


def test_concierge_write_mode_stays_with_l_action_journal():
    snapshot = runtime._concierge_snapshot({
        "requestId": "4ad046b3-06a5-4e62-a3ef-17a4f83dcdde",
        "route": {
            "resolverVersion": "test",
            "mode": "do",
            "selectedRoutes": [{
                "specialistKey": "calendar",
                "capability": "calendar_package",
                "role": "source",
            }],
        },
        "foundation": {"requiresFoundationBridge": False},
    })

    assert snapshot["dispatch_allowed"] is False
    assert snapshot["execution_owner"] == "l-durable-action-router"


def test_concierge_read_mode_can_dispatch_after_durable_commit():
    snapshot = runtime._concierge_snapshot({
        "requestId": "4ad046b3-06a5-4e62-a3ef-17a4f83dcdde",
        "route": {
            "resolverVersion": "test",
            "mode": "explore",
            "selectedRoutes": [{
                "specialistKey": "travel",
                "capability": "trip_planning",
                "role": "source",
            }],
        },
        "foundation": {"requiresFoundationBridge": True},
    })

    assert snapshot["dispatch_allowed"] is True
    assert snapshot["execution_owner"] == "concierge-read"


def test_concierge_results_become_one_l_capability_packet():
    route = runtime.concierge_route_packet({
        "status": "completed",
        "results": [{
            "specialist": "travel",
            "summary": "A specialist result.",
            "authoritative": True,
        }],
        "tasks": [],
    })

    assert route["handled"] is True
    assert route["capability"] == "shine_concierge"
    assert route["status"] == "ok"
    assert route["reply"] == "A specialist result."


def test_preflight_keeps_component_failures_fail_soft(monkeypatch):
    monkeypatch.setattr(
        runtime,
        "_foundation_snapshot",
        lambda db, user_id: {"status": "healthy", "specialists": []},
    )

    calls = []
    def fake_edge(slug, **kwargs):
        calls.append(slug)
        if slug == "concierge-intake":
            return {
                "requestId": "4ad046b3-06a5-4e62-a3ef-17a4f83dcdde",
                "route": {
                    "mode": "ask",
                    "selectedRoutes": [],
                    "resolverVersion": "test",
                },
                "foundation": {"requiresFoundationBridge": False},
            }
        raise RuntimeError("defence unavailable")

    monkeypatch.setattr(runtime, "_edge_post", fake_edge)
    monkeypatch.setattr(
        runtime,
        "_shine_ai_advisory",
        lambda **kwargs: {"status": "unavailable", "reason_code": "test"},
    )

    receipt = runtime.preflight_shine_request(
        object(),
        user_id="4ad046b3-06a5-4e62-a3ef-17a4f83dcdde",
        authorization="Bearer token",
        message="hello",
        request_id="4ad046b3-06a5-4e62-a3ef-17a4f83dcdde",
    )

    assert receipt["status"] == "degraded"
    assert receipt["components"]["l"]["status"] == "active"
    assert receipt["components"]["concierge"]["status"] == "planned"
    assert receipt["components"]["defence"]["status"] == "unavailable"
    assert receipt["components"]["shine_ai"]["status"] == "unavailable"
    assert calls == ["concierge-intake", "defence-companion"]



def test_runtime_trace_is_content_free_and_carries_shine_ai_attestation():
    digest = "a" * 64
    runtime_packet = {
        "version": runtime.RUNTIME_VERSION,
        "request_id": "4ad046b3-06a5-4e62-a3ef-17a4f83dcdde",
        "status": "ready",
        "warnings": [],
        "components": {
            "l": {
                "status": "active",
                "authority": "voice+synthesis+durable-task",
                "runtime": {
                    "provider": "railway",
                    "commit": "commit-1",
                    "branch": "main",
                    "deployment": "deploy-1",
                    "service": "Project-L-Modular",
                    "environment": "production",
                },
            },
            "foundation": {
                "status": "healthy",
                "specialist_count": 1,
                "executable_count": 1,
                "blocked_count": 0,
                "specialists": [{
                    "app_id": "shine-travel",
                    "capability_id": "trip_planning",
                    "executable": True,
                    "runtime_available": True,
                }],
            },
            "concierge": {
                "status": "planned",
                "request_id": "c5cce6c2-d07a-46bb-84c6-07b1bd8ec892",
                "resolver_version": "v1",
                "mode": "explore",
                "dispatch_allowed": True,
                "execution_owner": "concierge-read",
                "selected_routes": [{
                    "specialistKey": "travel",
                    "capability": "trip_planning",
                    "role": "source",
                }],
                "foundation_routes": ["trip_planning"],
            },
            "defence": {
                "status": "completed",
                "summary": "PRIVATE DEFENCE SUMMARY",
                "reviews": [{
                    "appId": "project-l",
                    "reviewCommitSha": "abc123",
                    "profileVersion": "1",
                    "status": "reviewed",
                    "limitation": "PRIVATE DEFENCE LIMITATION",
                }],
                "boundaries": {"snapshotOnly": True},
            },
            "shine_ai": {
                "status": "ok",
                "answer": "PRIVATE ADVISORY TEXT MUST NOT ENTER TRACE",
                "route": "model",
                "provider": "openai",
                "model": "example-model",
                "model_tier": "fast",
                "reason": "PRIVATE ROUTING REASON",
                "request_id": "ai-request-1",
                "decision_trace": {
                    "version": 1,
                    "algorithm": "sha256",
                    "scope": "control-plane",
                    "service_version": "1.37.0",
                    "service_release": "layer-137",
                    "planning_sha256": digest,
                    "recovery_sha256": digest,
                    "execution_sha256": digest,
                    "grounding_sha256": digest,
                    "verification_sha256": digest,
                    "delivery_sha256": digest,
                    "lineage_sha256": digest,
                },
            },
        },
    }
    execution = {
        "status": "completed",
        "request_id": "c5cce6c2-d07a-46bb-84c6-07b1bd8ec892",
        "tasks": [{
            "id": "task-1",
            "specialist_key": "travel",
            "status": "completed",
            "action_type": "read",
            "result_summary": "PRIVATE TASK SUMMARY",
        }],
        "results": [{
            "specialist": "travel",
            "result_type": "trip_plan",
            "summary": "PRIVATE SPECIALIST RESULT",
            "payload": {"secret": "PRIVATE PAYLOAD"},
            "authoritative": True,
        }],
    }

    trace = runtime.build_runtime_trace(runtime_packet, execution)
    rendered = json.dumps(trace, sort_keys=True)

    assert trace["version"] == runtime.RUNTIME_TRACE_VERSION
    assert trace["content_exposed"] is False
    assert trace["components"]["shine_ai"]["decision_lineage_sha256"] == digest
    assert trace["component_status"]["l"] == "active"
    assert "PRIVATE ADVISORY" not in rendered
    assert "PRIVATE TASK SUMMARY" not in rendered
    assert "PRIVATE SPECIALIST RESULT" not in rendered
    assert "PRIVATE PAYLOAD" not in rendered
    assert "PRIVATE DEFENCE SUMMARY" not in rendered
    assert "PRIVATE DEFENCE LIMITATION" not in rendered
    assert "PRIVATE ROUTING REASON" not in rendered


def test_runtime_trace_ignores_private_text_but_changes_on_control_plane_drift():
    base = {
        "version": runtime.RUNTIME_VERSION,
        "request_id": "4ad046b3-06a5-4e62-a3ef-17a4f83dcdde",
        "status": "ready",
        "warnings": [],
        "components": {
            "l": {"status": "active", "authority": "voice+synthesis+durable-task"},
            "foundation": {"status": "healthy", "specialists": []},
            "concierge": {
                "status": "planned",
                "mode": "ask",
                "dispatch_allowed": False,
                "execution_owner": "l-core",
                "selected_routes": [],
            },
            "defence": {"status": "completed", "summary": "one", "reviews": []},
            "shine_ai": {
                "status": "ok",
                "answer": "first private answer",
                "route": "model",
                "model_tier": "fast",
            },
        },
    }
    first = runtime.build_runtime_trace(base)

    changed_text = json.loads(json.dumps(base))
    changed_text["components"]["shine_ai"]["answer"] = "second private answer"
    assert runtime.build_runtime_trace(changed_text)["lineage_sha256"] == first["lineage_sha256"]

    changed_control = json.loads(json.dumps(base))
    changed_control["components"]["concierge"]["mode"] = "explore"
    assert runtime.build_runtime_trace(changed_control)["lineage_sha256"] != first["lineage_sha256"]
