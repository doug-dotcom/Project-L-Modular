"""Crash-safe Shine Foundation delegation renewal for native Companion."""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID

import httpx

DEFAULT_FOUNDATION_URL = (
    "https://sjpxqeyewahraxvidvcc.supabase.co/functions/v1/foundation-gateway"
)
MAX_RESPONSE_BYTES = 64 * 1024
HARD_DENIALS = frozenset({
    "refresh-reuse-detected",
    "refresh-credential-invalid",
    "integration-link-inactive",
    "refresh-request-conflict",
    "integration-client-unverified",
    "integration-client-mismatch",
})


def _uuid(value: Any) -> str:
    return str(UUID(str(value)))


def _rpc_data(db, name: str, params: dict | None = None):
    result = db.rpc(name, params or {}).execute()
    return getattr(result, "data", None)


def _single_secret(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) < 32 or len(value) > 8192:
        raise RuntimeError(f"{label}-unavailable")
    return value


def _foundation_url(value: str | None = None) -> str:
    url = str(value or os.getenv("SHINE_FOUNDATION_URL") or DEFAULT_FOUNDATION_URL).rstrip("/")
    if not url.startswith("https://"):
        raise RuntimeError("foundation-url-invalid")
    return url


def foundation_account_owner(db) -> str | None:
    """Resolve the provisioned L account that is allowed to own Foundation authority."""
    result = (
        db.table("l_account_config")
        .select("user_id")
        .eq("singleton", True)
        .limit(2)
        .execute()
    )
    rows = getattr(result, "data", None)
    if not isinstance(rows, list) or len(rows) != 1:
        return None
    value = (rows[0] or {}).get("user_id")
    if not value:
        return None
    return _uuid(value)


def foundation_connection_status(db, user_id: str) -> dict:
    state = _rpc_data(
        db,
        "companion_foundation_connection_state_v2",
        {"p_user_id": _uuid(user_id)},
    )
    if not isinstance(state, dict):
        raise RuntimeError("foundation-state-unavailable")
    return state


def _post_refresh(
    *,
    url: str,
    client_token: str,
    refresh_token: str,
    envelope: dict,
    timeout_seconds: float,
    post_impl=None,
):
    post = post_impl or httpx.post
    return post(
        url + "/v1/integration/delegation/refresh",
        headers={
            "Content-Type": "application/json",
            "X-Shine-Client-Token": client_token,
            "X-Shine-Refresh-Token": refresh_token,
        },
        json=envelope,
        timeout=timeout_seconds,
        follow_redirects=False,
    )


def _response_json(response) -> dict:
    declared = response.headers.get("content-length") if hasattr(response, "headers") else None
    try:
        if declared is not None and int(declared) > MAX_RESPONSE_BYTES:
            raise RuntimeError("foundation-response-too-large")
    except (TypeError, ValueError):
        pass

    raw = bytes(getattr(response, "content", b""))
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("foundation-response-too-large")

    try:
        data = response.json()
    except Exception as exc:
        raise RuntimeError("foundation-response-invalid") from exc
    if not isinstance(data, dict):
        raise RuntimeError("foundation-response-invalid")
    return data


def _delegation_token(db, user_id: str, link_request_id: str) -> str:
    return _single_secret(
        _rpc_data(
            db,
            "companion_foundation_delegation_token_v1",
            {
                "p_user_id": _uuid(user_id),
                "p_request_id": _uuid(link_request_id),
            },
        ),
        "foundation-delegation",
    )


def ensure_foundation_delegation(
    db,
    user_id: str,
    *,
    foundation_url: str | None = None,
    timeout_seconds: float = 12.0,
    skew_seconds: int = 300,
    post_impl=None,
) -> dict:
    """Return usable delegated authority, rotating it without widening consent.

    Network failures deliberately leave the staged rotation pending. A later call
    reuses the same request id, session id, refresh id and token hashes, allowing
    Foundation v2 to return its committed result idempotently.
    """
    owner_id = _uuid(user_id)
    if not isinstance(skew_seconds, int) or isinstance(skew_seconds, bool):
        raise ValueError("skew_seconds must be an integer")
    if skew_seconds < 0 or skew_seconds > 3600:
        raise ValueError("skew_seconds outside allowed range")

    claim = _rpc_data(
        db,
        "companion_claim_foundation_refresh_v2",
        {"p_user_id": owner_id, "p_skew_seconds": skew_seconds},
    )
    if not isinstance(claim, dict):
        raise RuntimeError("foundation-refresh-claim-unavailable")

    state = str(claim.get("state") or "")
    link_request_id = claim.get("requestId")

    if state == "active":
        token = _delegation_token(db, owner_id, link_request_id)
        return {
            "status": "active",
            "request_id": _uuid(link_request_id),
            "delegation_token": token,
            "delegation_expires_at": claim.get("delegationExpiresAt"),
            "refresh_expires_at": claim.get("refreshExpiresAt"),
            "refresh_generation": claim.get("refreshGeneration"),
            "refreshed": False,
        }

    if state in {"not-connected", "reconnect-required"}:
        return {
            "status": state,
            "reason_code": claim.get("reasonCode") or state,
            "refreshed": False,
        }

    if state == "busy":
        return {
            "status": "busy",
            "retry_after": claim.get("retryAfter"),
            "refreshed": False,
        }

    if state != "refresh-required":
        raise RuntimeError("foundation-refresh-state-invalid")

    rotation_request_id = _uuid(claim.get("rotationRequestId"))
    lease_token = _uuid(claim.get("leaseToken"))
    new_session_id = _uuid(claim.get("newSessionId"))
    new_refresh_id = _uuid(claim.get("newRefreshId"))
    delegation_hash = str(claim.get("newDelegationTokenHash") or "")
    refresh_hash = str(claim.get("newRefreshTokenHash") or "")
    if len(delegation_hash) != 64 or len(refresh_hash) != 64:
        raise RuntimeError("foundation-refresh-stage-invalid")

    current_refresh = _single_secret(
        _rpc_data(
            db,
            "companion_foundation_refresh_token_v1",
            {"p_user_id": owner_id, "p_request_id": _uuid(link_request_id)},
        ),
        "foundation-refresh",
    )
    client_token = _single_secret(
        _rpc_data(db, "concierge_foundation_client_token_v1"),
        "foundation-client",
    )

    envelope = {
        "integrationDelegationRefresh": "shine-foundation/integration-delegation-refresh-v2",
        "schemaVersion": "2.0.0",
        "requestId": rotation_request_id,
        "clientId": "shine.companion",
        "newSessionId": new_session_id,
        "newRefreshId": new_refresh_id,
        "newDelegationTokenHash": delegation_hash,
        "newRefreshTokenHash": refresh_hash,
    }

    try:
        response = _post_refresh(
            url=_foundation_url(foundation_url),
            client_token=client_token,
            refresh_token=current_refresh,
            envelope=envelope,
            timeout_seconds=timeout_seconds,
            post_impl=post_impl,
        )
        body = _response_json(response)
    except (httpx.HTTPError, RuntimeError) as exc:
        # Pending state and candidate secrets stay durable for exact retry.
        return {
            "status": "unavailable",
            "reason_code": str(exc) or "foundation-unavailable",
            "refreshed": False,
            "retry_safe": True,
        }

    reason = str(body.get("reasonCode") or "foundation-refresh-failed")
    if response.status_code == 200 and body.get("status") == "refreshed":
        if _uuid(body.get("requestId")) != rotation_request_id:
            raise RuntimeError("foundation-refresh-request-mismatch")
        if _uuid(body.get("sessionId")) != new_session_id:
            raise RuntimeError("foundation-refresh-session-mismatch")
        if _uuid(body.get("refreshId")) != new_refresh_id:
            raise RuntimeError("foundation-refresh-id-mismatch")

        completion = _rpc_data(
            db,
            "companion_complete_foundation_refresh_v2",
            {
                "p_user_id": owner_id,
                "p_rotation_request_id": rotation_request_id,
                "p_lease_token": lease_token,
                "p_delegation_expires_at": body.get("expiresAt"),
                "p_refresh_expires_at": body.get("refreshExpiresAt"),
                "p_refresh_generation": int(body.get("refreshGeneration")),
                "p_reason_code": reason,
            },
        )
        if not isinstance(completion, dict) or completion.get("completed") is not True:
            raise RuntimeError("foundation-refresh-local-commit-failed")

        token = _delegation_token(db, owner_id, link_request_id)
        return {
            "status": "active",
            "request_id": _uuid(link_request_id),
            "delegation_token": token,
            "delegation_expires_at": body.get("expiresAt"),
            "refresh_expires_at": body.get("refreshExpiresAt"),
            "refresh_generation": body.get("refreshGeneration"),
            "refreshed": True,
            "replayed": bool(body.get("replayed")),
            "reason_code": reason,
        }

    if reason in HARD_DENIALS:
        _rpc_data(
            db,
            "companion_fail_foundation_refresh_v2",
            {
                "p_user_id": owner_id,
                "p_rotation_request_id": rotation_request_id,
                "p_lease_token": lease_token,
                "p_reason_code": reason,
            },
        )
        return {
            "status": "reconnect-required",
            "reason_code": reason,
            "refreshed": False,
        }

    # Unknown/transient remote failures preserve the pending request for retry.
    return {
        "status": "unavailable",
        "reason_code": reason,
        "http_status": int(response.status_code),
        "refreshed": False,
        "retry_safe": True,
    }


def safe_connection_result(result: dict) -> dict:
    """Strip bearer/delegation material before returning status to HTTP callers."""
    return {key: value for key, value in result.items() if key != "delegation_token"}



def foundation_fleet_status(
    db,
    user_id: str,
    *,
    foundation_url: str | None = None,
    timeout_seconds: float = 5.0,
    get_impl=None,
) -> dict:
    """Return the live Concierge specialist fleet for this bound Companion user.

    The response is deliberately projected: bearer/client credentials, delegation
    tokens, grant UUIDs and adapter endpoints never leave this service boundary.
    """
    owner_id = _uuid(user_id)
    authority = ensure_foundation_delegation(
        db,
        owner_id,
        foundation_url=foundation_url,
        timeout_seconds=timeout_seconds,
    )
    if authority.get("status") != "active":
        return {
            "status": str(authority.get("status") or "unavailable"),
            "reason_code": str(authority.get("reason_code") or "foundation-authority-unavailable"),
            "specialist_count": 0,
            "executable_count": 0,
            "blocked_count": 0,
            "specialists": [],
        }

    client_token = _single_secret(
        _rpc_data(db, "concierge_foundation_client_token_v1"),
        "foundation-client",
    )
    delegation_token = _single_secret(
        authority.get("delegation_token"),
        "foundation-delegation",
    )
    get = get_impl or httpx.get
    url = _foundation_url(foundation_url) + (
        "/v1/concierge/fleet"
        "?clientId=shine.companion"
        "&purpose=concierge.cross-project-read"
    )

    try:
        response = get(
            url,
            headers={
                "X-Shine-Client-Token": client_token,
                "X-Shine-Delegation-Token": delegation_token,
            },
            timeout=timeout_seconds,
            follow_redirects=False,
        )
        body = _response_json(response)
    except (httpx.HTTPError, RuntimeError):
        return {
            "status": "unavailable",
            "reason_code": "concierge-fleet-unavailable",
            "specialist_count": 0,
            "executable_count": 0,
            "blocked_count": 0,
            "specialists": [],
        }

    if response.status_code != 200 or body.get("status") != "ok":
        return {
            "status": "unavailable",
            "reason_code": str(body.get("reasonCode") or "concierge-fleet-unavailable"),
            "specialist_count": 0,
            "executable_count": 0,
            "blocked_count": 0,
            "specialists": [],
        }

    fleet = body.get("fleet")
    if not isinstance(fleet, dict):
        raise RuntimeError("foundation-fleet-response-invalid")
    raw_specialists = fleet.get("specialists")
    if not isinstance(raw_specialists, list) or len(raw_specialists) > 20:
        raise RuntimeError("foundation-fleet-response-invalid")

    specialists = []
    for item in raw_specialists:
        if not isinstance(item, dict):
            raise RuntimeError("foundation-fleet-response-invalid")
        capability_id = str(item.get("capabilityId") or "")
        app_id = str(item.get("appId") or "")
        if not capability_id or not app_id:
            raise RuntimeError("foundation-fleet-response-invalid")
        runtime = item.get("runtimeStatus") if isinstance(item.get("runtimeStatus"), dict) else {}
        specialists.append({
            "app_id": app_id,
            "app_name": str(item.get("appName") or app_id),
            "capability_id": capability_id,
            "display_name": str(item.get("displayName") or capability_id),
            "mode": str(item.get("mode") or "advisory"),
            "executable": item.get("executable") is True,
            "reason_code": str(item.get("reasonCode") or "unknown"),
            "grant_status": str(item.get("grantStatus") or "missing"),
            "runtime_available": runtime.get("available") is True,
            "runtime_reason_code": str(runtime.get("reasonCode") or "unknown"),
        })

    specialist_count = int(fleet.get("specialistCount") or len(specialists))
    executable_count = int(fleet.get("executableCount") or sum(1 for row in specialists if row["executable"]))
    blocked_count = int(fleet.get("blockedCount") or max(0, specialist_count - executable_count))
    if specialist_count != len(specialists) or executable_count < 0 or blocked_count < 0:
        raise RuntimeError("foundation-fleet-response-invalid")

    return {
        "status": "healthy" if blocked_count == 0 else "degraded",
        "reason_code": "concierge-fleet-ready" if blocked_count == 0 else "concierge-fleet-degraded",
        "specialist_count": specialist_count,
        "executable_count": executable_count,
        "blocked_count": blocked_count,
        "specialists": specialists,
    }


def executable_foundation_capabilities(fleet: dict | None) -> set[str]:
    if not isinstance(fleet, dict):
        return set()
    specialists = fleet.get("specialists")
    if not isinstance(specialists, list):
        return set()
    return {
        str(item.get("capability_id"))
        for item in specialists
        if isinstance(item, dict)
        and item.get("executable") is True
        and item.get("capability_id")
    }
