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
