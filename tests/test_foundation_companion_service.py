import json
from types import SimpleNamespace

import httpx
import pytest

from services.foundation_companion_service import (
    ensure_foundation_delegation,
    safe_connection_result,
)


USER = "11111111-1111-4111-8111-111111111111"
LINK = "22222222-2222-4222-8222-222222222222"
ROTATION = "33333333-3333-4333-8333-333333333333"
SESSION = "44444444-4444-4444-8444-444444444444"
REFRESH = "55555555-5555-4555-8555-555555555555"
LEASE = "66666666-6666-4666-8666-666666666666"


class Result:
    def __init__(self, data):
        self.data = data


class Rpc:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return Result(self.data)


class FakeDb:
    def __init__(self, claim, *, current_refresh="r" * 128, client_token="c" * 128,
                 delegation="d" * 128):
        self.claim = claim
        self.current_refresh = current_refresh
        self.client_token = client_token
        self.delegation = delegation
        self.calls = []

    def rpc(self, name, params=None):
        self.calls.append((name, params or {}))
        if name == "companion_claim_foundation_refresh_v2":
            return Rpc(self.claim)
        if name == "companion_foundation_refresh_token_v1":
            return Rpc(self.current_refresh)
        if name == "concierge_foundation_client_token_v1":
            return Rpc(self.client_token)
        if name == "companion_foundation_delegation_token_v1":
            return Rpc(self.delegation)
        if name == "companion_complete_foundation_refresh_v2":
            return Rpc({"completed": True})
        if name == "companion_fail_foundation_refresh_v2":
            return Rpc({"failed": True})
        raise AssertionError(name)


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {"content-length": str(len(self.content))}

    def json(self):
        return self._payload


def active_claim():
    return {
        "state": "active",
        "requestId": LINK,
        "delegationExpiresAt": "2026-09-28T00:00:00Z",
        "refreshExpiresAt": "2026-10-27T00:00:00Z",
        "refreshGeneration": 1,
    }


def refresh_claim():
    return {
        "state": "refresh-required",
        "requestId": LINK,
        "rotationRequestId": ROTATION,
        "newSessionId": SESSION,
        "newRefreshId": REFRESH,
        "newDelegationTokenHash": "a" * 64,
        "newRefreshTokenHash": "b" * 64,
        "leaseToken": LEASE,
        "reusedPending": False,
    }


def test_active_delegation_is_reused_without_network():
    db = FakeDb(active_claim())

    def forbidden(*args, **kwargs):
        raise AssertionError("network should not be used")

    result = ensure_foundation_delegation(db, USER, post_impl=forbidden)

    assert result["status"] == "active"
    assert result["refreshed"] is False
    assert result["delegation_token"] == "d" * 128
    assert "companion_foundation_refresh_token_v1" not in [name for name, _ in db.calls]


def test_expired_delegation_rotates_with_header_only_old_refresh():
    db = FakeDb(refresh_claim())
    seen = {}

    def post(url, *, headers, json, timeout, follow_redirects):
        seen.update(url=url, headers=headers, body=json, timeout=timeout,
                    follow_redirects=follow_redirects)
        return FakeResponse(200, {
            "integrationResponse": "shine-foundation/integration-delegation-refresh-response-v2",
            "schemaVersion": "2.0.0",
            "status": "refreshed",
            "reasonCode": "refresh-credential-rotated-v2",
            "requestId": ROTATION,
            "linkRequestId": LINK,
            "sessionId": SESSION,
            "refreshId": REFRESH,
            "expiresAt": "2026-09-28T11:00:00Z",
            "refreshExpiresAt": "2026-12-26T11:00:00Z",
            "refreshGeneration": 2,
            "replayed": False,
        })

    result = ensure_foundation_delegation(db, USER, post_impl=post)

    assert result["status"] == "active"
    assert result["refreshed"] is True
    assert result["refresh_generation"] == 2
    assert seen["headers"]["X-Shine-Refresh-Token"] == "r" * 128
    assert seen["headers"]["X-Shine-Client-Token"] == "c" * 128
    assert "refreshToken" not in seen["body"]
    assert "delegationToken" not in seen["body"]
    assert seen["body"]["newDelegationTokenHash"] == "a" * 64
    assert any(name == "companion_complete_foundation_refresh_v2" for name, _ in db.calls)


def test_network_failure_preserves_pending_rotation_for_exact_retry():
    db = FakeDb(refresh_claim())

    def offline(*args, **kwargs):
        raise httpx.ConnectError("offline")

    result = ensure_foundation_delegation(db, USER, post_impl=offline)

    assert result["status"] == "unavailable"
    assert result["retry_safe"] is True
    assert not any(name == "companion_fail_foundation_refresh_v2" for name, _ in db.calls)
    assert not any(name == "companion_complete_foundation_refresh_v2" for name, _ in db.calls)


def test_replay_denial_quarantines_local_connection():
    db = FakeDb(refresh_claim())

    def denied(*args, **kwargs):
        return FakeResponse(403, {
            "status": "denied",
            "reasonCode": "refresh-reuse-detected",
        })

    result = ensure_foundation_delegation(db, USER, post_impl=denied)

    assert result == {
        "status": "reconnect-required",
        "reason_code": "refresh-reuse-detected",
        "refreshed": False,
    }
    assert any(name == "companion_fail_foundation_refresh_v2" for name, _ in db.calls)


def test_status_projection_never_returns_delegation_secret():
    safe = safe_connection_result({
        "status": "active",
        "delegation_token": "secret",
        "refreshed": True,
    })
    assert safe == {"status": "active", "refreshed": True}


@pytest.mark.parametrize("value", [-1, 3601, True, 2.5])
def test_refresh_skew_is_bounded(value):
    with pytest.raises(ValueError):
        ensure_foundation_delegation(FakeDb(active_claim()), USER, skew_seconds=value)
