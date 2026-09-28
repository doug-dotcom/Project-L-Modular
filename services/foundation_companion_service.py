"""Crash-safe Shine Foundation delegation renewal for native Companion."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
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



def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _concierge_authority(db, user_id: str, *, foundation_url=None, timeout_seconds=12.0) -> dict:
    authority = ensure_foundation_delegation(
        db,
        _uuid(user_id),
        foundation_url=foundation_url,
        timeout_seconds=timeout_seconds,
    )
    if authority.get("status") != "active":
        return {
            "status": str(authority.get("status") or "unavailable"),
            "reason_code": str(authority.get("reason_code") or "foundation-authority-unavailable"),
        }
    return {
        "status": "active",
        "link_request_id": _uuid(authority.get("request_id")),
        "client_token": _single_secret(
            _rpc_data(db, "concierge_foundation_client_token_v1"),
            "foundation-client",
        ),
        "delegation_token": _single_secret(
            authority.get("delegation_token"),
            "foundation-delegation",
        ),
    }


def _post_concierge(
    *,
    path: str,
    envelope: dict,
    client_token: str,
    delegation_token: str,
    foundation_url: str | None,
    timeout_seconds: float,
    post_impl=None,
):
    post = post_impl or httpx.post
    return post(
        _foundation_url(foundation_url) + path,
        headers={
            "Content-Type": "application/json",
            "X-Shine-Client-Token": client_token,
            "X-Shine-Delegation-Token": delegation_token,
        },
        json=envelope,
        timeout=timeout_seconds,
        follow_redirects=False,
    )


def invoke_foundation_specialist(
    db,
    user_id: str,
    *,
    request_id: str,
    capability_id: str,
    input_data: dict,
    foundation_url: str | None = None,
    timeout_seconds: float = 120.0,
    post_impl=None,
) -> dict:
    """Plan and execute exactly one already-consented advisory specialist.

    Project L never calls specialist endpoints directly. Foundation performs the
    grant/consent/runtime gate, issues the one-time invocation ticket and records
    execution. This function returns only a bounded result projection.
    """
    request_id = _uuid(request_id)
    capability_id = str(capability_id or "")
    if (
        not capability_id
        or len(capability_id) > 128
        or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for ch in capability_id)
    ):
        raise ValueError("invalid capability id")
    if not isinstance(input_data, dict):
        raise ValueError("specialist input must be an object")
    try:
        encoded_input = json.dumps(input_data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("specialist input must be JSON serialisable") from exc
    if len(encoded_input) > 12000:
        raise ValueError("specialist input too large")
    if timeout_seconds < 1 or timeout_seconds > 180:
        raise ValueError("timeout outside allowed range")

    authority = _concierge_authority(
        db,
        user_id,
        foundation_url=foundation_url,
        timeout_seconds=min(timeout_seconds, 12.0),
    )
    if authority.get("status") != "active":
        return {
            "status": authority.get("status"),
            "reason_code": authority.get("reason_code"),
            "capability_id": capability_id,
            "request_id": request_id,
        }

    requested_at = _utc_now()
    plan_envelope = {
        "conciergePlan": "shine-concierge/plan-v1",
        "schemaVersion": "1.0.0",
        "requestId": request_id,
        "clientId": "shine.companion",
        "purpose": "concierge.cross-project-read",
        "capabilityIds": [capability_id],
        "requestedAt": requested_at,
    }
    try:
        plan_response = _post_concierge(
            path="/v1/concierge/plan",
            envelope=plan_envelope,
            client_token=authority["client_token"],
            delegation_token=authority["delegation_token"],
            foundation_url=foundation_url,
            timeout_seconds=min(timeout_seconds, 20.0),
            post_impl=post_impl,
        )
        plan_body = _response_json(plan_response)
    except (httpx.HTTPError, RuntimeError):
        return {
            "status": "unavailable",
            "reason_code": "concierge-plan-unavailable",
            "capability_id": capability_id,
            "request_id": request_id,
        }

    if plan_response.status_code != 200 or plan_body.get("status") != "planned":
        return {
            "status": str(plan_body.get("status") or "unavailable"),
            "reason_code": str(plan_body.get("reasonCode") or "concierge-plan-rejected"),
            "capability_id": capability_id,
            "request_id": request_id,
        }

    execute_envelope = {
        "conciergeExecute": "shine-concierge/execute-v1",
        "schemaVersion": "1.0.0",
        "requestId": request_id,
        "clientId": "shine.companion",
        "inputs": {capability_id: input_data},
        "requestedAt": _utc_now(),
    }
    try:
        execute_response = _post_concierge(
            path="/v1/concierge/execute",
            envelope=execute_envelope,
            client_token=authority["client_token"],
            delegation_token=authority["delegation_token"],
            foundation_url=foundation_url,
            timeout_seconds=timeout_seconds,
            post_impl=post_impl,
        )
        execute_body = _response_json(execute_response)
    except (httpx.HTTPError, RuntimeError):
        return {
            "status": "unavailable",
            "reason_code": "concierge-execution-unavailable",
            "capability_id": capability_id,
            "request_id": request_id,
        }

    status = str(execute_body.get("status") or "unavailable")
    reason = str(execute_body.get("reasonCode") or "concierge-execution-unavailable")
    safe = {
        "status": status,
        "reason_code": reason,
        "capability_id": capability_id,
        "request_id": request_id,
    }
    results = execute_body.get("results")
    if isinstance(results, list):
        matches = [
            row for row in results
            if isinstance(row, dict) and row.get("capabilityId") == capability_id
        ]
        if len(matches) == 1:
            row = matches[0]
            safe["specialist_status"] = str(row.get("status") or "")
            safe["specialist_reason_code"] = str(row.get("reasonCode") or "")
            if isinstance(row.get("result"), dict):
                safe["result"] = row["result"]

    if status == "completed" and "result" not in safe:
        return {
            **safe,
            "status": "unavailable",
            "reason_code": "concierge-result-missing",
        }
    return safe



MAX_CONCIERGE_EXECUTION_STEPS = 4
MAX_CONCIERGE_INPUT_BYTES = 12 * 1024


def _valid_capability_id(value: str) -> bool:
    return bool(
        value
        and len(value) <= 128
        and all(ch in "abcdefghijklmnopqrstuvwxyz0123456789._-" for ch in value)
    )


def _normalise_concierge_execution_plan(orchestration_plan: dict) -> dict:
    """Validate a planner packet and derive the exact Foundation execution subset."""
    if not isinstance(orchestration_plan, dict):
        raise ValueError("concierge plan must be an object")

    selected = orchestration_plan.get("selected_capabilities")
    steps = orchestration_plan.get("steps")
    if (
        not isinstance(selected, list)
        or not isinstance(steps, list)
        or len(selected) < 1
        or len(selected) > MAX_CONCIERGE_EXECUTION_STEPS
        or len(steps) != len(selected)
    ):
        raise ValueError("invalid concierge plan shape")

    selected_ids = [str(value or "") for value in selected]
    if (
        len(set(selected_ids)) != len(selected_ids)
        or any(not _valid_capability_id(value) for value in selected_ids)
    ):
        raise ValueError("invalid concierge capability selection")

    by_capability = {}
    for raw in steps:
        if not isinstance(raw, dict):
            raise ValueError("invalid concierge step")
        capability_id = str(raw.get("capability_id") or "")
        if capability_id in by_capability or capability_id not in selected_ids:
            raise ValueError("concierge step capability mismatch")
        by_capability[capability_id] = raw

    if set(by_capability) != set(selected_ids):
        raise ValueError("concierge step set mismatch")

    executable = []
    skipped = []
    for capability_id in selected_ids:
        step = by_capability[capability_id]
        step_status = str(step.get("status") or "")
        reason_code = str(step.get("reason_code") or "unknown")[:160]
        app_name = str(step.get("app_name") or "")[:120]
        display_name = str(step.get("display_name") or capability_id)[:160]
        if step_status == "ready":
            contract = step.get("input_contract")
            if (
                not isinstance(contract, dict)
                or contract.get("status") != "ready"
                or not isinstance(contract.get("input_data"), dict)
            ):
                raise ValueError("ready concierge step missing compiled input")
            input_data = contract["input_data"]
            try:
                encoded = json.dumps(
                    input_data,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise ValueError("concierge input must be JSON serialisable") from exc
            if len(encoded) > MAX_CONCIERGE_INPUT_BYTES:
                raise ValueError("concierge input too large")
            executable.append({
                "capability_id": capability_id,
                "app_name": app_name,
                "display_name": display_name,
                "input_data": input_data,
            })
            continue

        contract = step.get("input_contract")
        missing_fields = (
            list(contract.get("missing_fields") or [])[:8]
            if isinstance(contract, dict)
            else []
        )
        skipped.append({
            "capability_id": capability_id,
            "app_name": app_name,
            "display_name": display_name,
            "status": step_status or "blocked",
            "reason_code": reason_code,
            "missing_fields": [str(field)[:80] for field in missing_fields],
        })

    return {
        "selected_capabilities": selected_ids,
        "executable": executable,
        "skipped": skipped,
    }


def _safe_foundation_execution_results(
    execute_body: dict,
    *,
    requested_capabilities: list[str],
    metadata_by_capability: dict[str, dict],
) -> list[dict]:
    raw_results = execute_body.get("results")
    if not isinstance(raw_results, list) or len(raw_results) > MAX_CONCIERGE_EXECUTION_STEPS:
        raise RuntimeError("concierge-results-invalid")

    seen = set()
    safe_results = []
    for raw in raw_results:
        if not isinstance(raw, dict):
            raise RuntimeError("concierge-results-invalid")
        capability_id = str(raw.get("capabilityId") or "")
        if (
            capability_id not in requested_capabilities
            or capability_id in seen
            or not _valid_capability_id(capability_id)
        ):
            raise RuntimeError("concierge-results-invalid")
        seen.add(capability_id)
        status = str(raw.get("status") or "failed")[:80]
        reason_code = str(raw.get("reasonCode") or "unknown")[:160]
        metadata = metadata_by_capability.get(capability_id, {})
        row = {
            "capability_id": capability_id,
            "app_id": str(raw.get("appId") or "")[:128],
            "app_name": str(metadata.get("app_name") or "")[:120],
            "display_name": str(metadata.get("display_name") or capability_id)[:160],
            "status": status,
            "reason_code": reason_code,
            "reused": raw.get("reused") is True,
        }
        result = raw.get("result")
        if result is not None:
            if not isinstance(result, dict):
                raise RuntimeError("concierge-results-invalid")
            row["result"] = result
        safe_results.append(row)
    return safe_results


def _pending_job_rows(result) -> list[dict]:
    data = getattr(result, "data", None)
    return data if isinstance(data, list) else []


def _store_pending_concierge_job(
    db,
    *,
    user_id: str,
    job_id: str,
    link_request_id: str,
    capability_ids: list[str],
    inputs: dict,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
) -> None:
    existing = (
        db.table("companion_foundation_pending_jobs")
        .select(
            "job_id,user_id,link_request_id,purpose,capability_ids,inputs,"
            "source_conversation_id,source_message_id,status"
        )
        .eq("job_id", job_id)
        .limit(2)
        .execute()
    )
    rows = _pending_job_rows(existing)
    if rows:
        if len(rows) != 1 or not isinstance(rows[0], dict):
            raise RuntimeError("concierge-local-job-ambiguous")
        row = rows[0]
        exact = (
            str(row.get("user_id") or "") == user_id
            and str(row.get("link_request_id") or "") == link_request_id
            and str(row.get("purpose") or "") == "concierge.cross-project-read"
            and list(row.get("capability_ids") or []) == capability_ids
            and dict(row.get("inputs") or {}) == inputs
            and str(row.get("source_conversation_id") or "") == str(source_conversation_id or "")
            and str(row.get("source_message_id") or "") == str(source_message_id or "")
        )
        if not exact:
            raise RuntimeError("concierge-local-replay-conflict")
        return

    db.table("companion_foundation_pending_jobs").insert({
        "job_id": job_id,
        "user_id": user_id,
        "link_request_id": link_request_id,
        "purpose": "concierge.cross-project-read",
        "capability_ids": capability_ids,
        "inputs": inputs,
        "source_conversation_id": (
            str(source_conversation_id)[:180]
            if source_conversation_id is not None
            else None
        ),
        "source_message_id": (
            str(source_message_id)[:180]
            if source_message_id is not None
            else None
        ),
        "status": "ready",
    }).execute()


def set_pending_concierge_job_status(
    db,
    *,
    user_id: str,
    job_id: str,
    status: str,
) -> None:
    if status not in {"ready", "completed", "failed", "cancelled"}:
        raise ValueError("invalid pending concierge job status")
    now = _utc_now()
    values = {
        "status": status,
        "updated_at": now,
        "completed_at": now if status in {"completed", "failed", "cancelled"} else None,
    }
    (
        db.table("companion_foundation_pending_jobs")
        .update(values)
        .eq("job_id", job_id)
        .eq("user_id", user_id)
        .execute()
    )


def invoke_foundation_orchestration(
    db,
    user_id: str,
    *,
    request_id: str,
    orchestration_plan: dict,
    foundation_url: str | None = None,
    timeout_seconds: float = 180.0,
    post_impl=None,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
) -> dict:
    """Execute the ready subset of one validated Concierge plan through Foundation.

    There is exactly one Foundation plan request and, when that succeeds, one
    Foundation execute request. Project L never calls specialist endpoints.
    Local blocked/missing-input steps are retained as skipped work and force a
    partial disclosure if any other specialist completes.
    """
    request_id = _uuid(request_id)
    if timeout_seconds < 1 or timeout_seconds > 180:
        raise ValueError("timeout outside allowed range")
    normalised = _normalise_concierge_execution_plan(orchestration_plan)
    executable = normalised["executable"]
    skipped = normalised["skipped"]

    if not executable:
        status = "needs_input" if any(
            step["status"] == "needs_input" for step in skipped
        ) else "blocked"
        return {
            "status": status,
            "reason_code": (
                "concierge-execution-needs-input"
                if status == "needs_input"
                else "concierge-execution-blocked"
            ),
            "foundation_status": "not_invoked",
            "request_id": request_id,
            "selected_capabilities": normalised["selected_capabilities"],
            "executed_capabilities": [],
            "completed_capabilities": [],
            "unavailable_capabilities": [],
            "skipped_capabilities": skipped,
            "results": [],
            "execution_performed": False,
            "synthesis_ready": False,
            "synthesis_must_disclose_partial": bool(skipped),
        }

    authority = _concierge_authority(
        db,
        user_id,
        foundation_url=foundation_url,
        timeout_seconds=min(timeout_seconds, 12.0),
    )
    if authority.get("status") != "active":
        return {
            "status": str(authority.get("status") or "unavailable"),
            "reason_code": str(
                authority.get("reason_code") or "foundation-authority-unavailable"
            ),
            "foundation_status": "not_invoked",
            "request_id": request_id,
            "selected_capabilities": normalised["selected_capabilities"],
            "executed_capabilities": [],
            "completed_capabilities": [],
            "unavailable_capabilities": [],
            "skipped_capabilities": skipped,
            "results": [],
            "execution_performed": False,
            "synthesis_ready": False,
            "synthesis_must_disclose_partial": bool(skipped),
        }

    capability_ids = [step["capability_id"] for step in executable]
    inputs = {
        step["capability_id"]: step["input_data"]
        for step in executable
    }
    metadata_by_capability = {
        step["capability_id"]: step
        for step in executable
    }

    plan_envelope = {
        "conciergePlan": "shine-concierge/plan-v1",
        "schemaVersion": "1.0.0",
        "requestId": request_id,
        "clientId": "shine.companion",
        "purpose": "concierge.cross-project-read",
        "capabilityIds": capability_ids,
        "requestedAt": _utc_now(),
    }
    try:
        plan_response = _post_concierge(
            path="/v1/concierge/plan",
            envelope=plan_envelope,
            client_token=authority["client_token"],
            delegation_token=authority["delegation_token"],
            foundation_url=foundation_url,
            timeout_seconds=min(timeout_seconds, 20.0),
            post_impl=post_impl,
        )
        plan_body = _response_json(plan_response)
    except (httpx.HTTPError, RuntimeError):
        return {
            "status": "unavailable",
            "reason_code": "concierge-plan-unavailable",
            "foundation_status": "unavailable",
            "request_id": request_id,
            "selected_capabilities": normalised["selected_capabilities"],
            "executed_capabilities": [],
            "completed_capabilities": [],
            "unavailable_capabilities": [],
            "skipped_capabilities": skipped,
            "results": [],
            "execution_performed": False,
            "synthesis_ready": False,
            "synthesis_must_disclose_partial": bool(skipped),
        }

    if plan_response.status_code != 200 or plan_body.get("status") != "planned":
        return {
            "status": str(plan_body.get("status") or "unavailable"),
            "reason_code": str(
                plan_body.get("reasonCode") or "concierge-plan-rejected"
            ),
            "foundation_status": str(plan_body.get("status") or "unavailable"),
            "request_id": request_id,
            "selected_capabilities": normalised["selected_capabilities"],
            "executed_capabilities": [],
            "completed_capabilities": [],
            "unavailable_capabilities": [],
            "skipped_capabilities": skipped,
            "results": [],
            "execution_performed": False,
            "synthesis_ready": False,
            "synthesis_must_disclose_partial": bool(skipped),
        }

    try:
        _store_pending_concierge_job(
            db,
            user_id=_uuid(user_id),
            job_id=request_id,
            link_request_id=authority["link_request_id"],
            capability_ids=capability_ids,
            inputs=inputs,
            source_conversation_id=source_conversation_id,
            source_message_id=source_message_id,
        )
    except Exception:
        return {
            "status": "unavailable",
            "reason_code": "concierge-retry-context-persist-failed",
            "foundation_status": "planned",
            "request_id": request_id,
            "selected_capabilities": normalised["selected_capabilities"],
            "executed_capabilities": [],
            "completed_capabilities": [],
            "unavailable_capabilities": capability_ids,
            "skipped_capabilities": skipped,
            "results": [],
            "execution_performed": False,
            "synthesis_ready": False,
            "synthesis_must_disclose_partial": bool(skipped),
        }

    execute_envelope = {
        "conciergeExecute": "shine-concierge/execute-v1",
        "schemaVersion": "1.0.0",
        "requestId": request_id,
        "clientId": "shine.companion",
        "inputs": inputs,
        "requestedAt": _utc_now(),
    }
    try:
        execute_response = _post_concierge(
            path="/v1/concierge/execute",
            envelope=execute_envelope,
            client_token=authority["client_token"],
            delegation_token=authority["delegation_token"],
            foundation_url=foundation_url,
            timeout_seconds=timeout_seconds,
            post_impl=post_impl,
        )
        execute_body = _response_json(execute_response)
    except (httpx.HTTPError, RuntimeError):
        return {
            "status": "unavailable",
            "reason_code": "concierge-execution-unavailable",
            "foundation_status": "unavailable",
            "request_id": request_id,
            "selected_capabilities": normalised["selected_capabilities"],
            "executed_capabilities": capability_ids,
            "completed_capabilities": [],
            "unavailable_capabilities": capability_ids,
            "skipped_capabilities": skipped,
            "results": [],
            "execution_performed": True,
            "synthesis_ready": False,
            "synthesis_must_disclose_partial": bool(skipped),
        }

    foundation_status = str(execute_body.get("status") or "unavailable")
    foundation_reason = str(
        execute_body.get("reasonCode") or "concierge-execution-unavailable"
    )
    if foundation_status not in {
        "completed", "partial", "failed", "blocked", "denied", "invalid", "unavailable"
    }:
        foundation_status = "unavailable"
        foundation_reason = "concierge-execution-status-invalid"

    raw_results = execute_body.get("results")
    if foundation_status not in {"completed", "partial"} and raw_results is None:
        return {
            "status": foundation_status,
            "reason_code": foundation_reason,
            "foundation_status": foundation_status,
            "foundation_reason_code": foundation_reason,
            "request_id": request_id,
            "selected_capabilities": normalised["selected_capabilities"],
            "executed_capabilities": capability_ids,
            "completed_capabilities": [],
            "unavailable_capabilities": capability_ids,
            "skipped_capabilities": skipped,
            "results": [],
            "execution_performed": True,
            "synthesis_ready": False,
            "synthesis_must_disclose_partial": bool(skipped),
        }

    try:
        safe_results = _safe_foundation_execution_results(
            execute_body,
            requested_capabilities=capability_ids,
            metadata_by_capability=metadata_by_capability,
        )
    except RuntimeError:
        return {
            "status": "unavailable",
            "reason_code": "concierge-results-invalid",
            "foundation_status": foundation_status,
            "request_id": request_id,
            "selected_capabilities": normalised["selected_capabilities"],
            "executed_capabilities": capability_ids,
            "completed_capabilities": [],
            "unavailable_capabilities": capability_ids,
            "skipped_capabilities": skipped,
            "results": [],
            "execution_performed": True,
            "synthesis_ready": False,
            "synthesis_must_disclose_partial": bool(skipped),
        }

    completed = [
        row["capability_id"]
        for row in safe_results
        if row["status"] == "completed" and isinstance(row.get("result"), dict)
    ]
    unavailable = [
        row["capability_id"]
        for row in safe_results
        if row["capability_id"] not in completed
    ]
    missing_result_ids = [
        capability_id
        for capability_id in capability_ids
        if capability_id not in {row["capability_id"] for row in safe_results}
    ]
    unavailable.extend(
        capability_id
        for capability_id in missing_result_ids
        if capability_id not in unavailable
    )

    if foundation_status == "completed" and (
        len(completed) != len(capability_ids) or unavailable
    ):
        return {
            "status": "unavailable",
            "reason_code": "concierge-results-incomplete",
            "foundation_status": foundation_status,
            "request_id": request_id,
            "selected_capabilities": normalised["selected_capabilities"],
            "executed_capabilities": capability_ids,
            "completed_capabilities": completed,
            "unavailable_capabilities": unavailable,
            "skipped_capabilities": skipped,
            "results": safe_results,
            "execution_performed": True,
            "synthesis_ready": bool(completed),
            "synthesis_must_disclose_partial": True,
        }

    partial = bool(skipped or unavailable or foundation_status == "partial")
    synthesis_ready = bool(completed) and foundation_status in {"completed", "partial"}
    status = (
        "partial"
        if synthesis_ready and partial
        else "completed"
        if synthesis_ready
        else foundation_status
    )
    reason_code = (
        "concierge-execution-partial"
        if status == "partial"
        else foundation_reason
    )

    retry = execute_body.get("retry")
    retry_scheduled = isinstance(retry, dict) and bool(retry)
    return {
        "status": status,
        "reason_code": reason_code,
        "foundation_status": foundation_status,
        "foundation_reason_code": foundation_reason,
        "request_id": request_id,
        "selected_capabilities": normalised["selected_capabilities"],
        "executed_capabilities": capability_ids,
        "completed_capabilities": completed,
        "unavailable_capabilities": unavailable,
        "skipped_capabilities": skipped,
        "results": safe_results,
        "execution_performed": True,
        "retry_scheduled": retry_scheduled,
        "synthesis_ready": synthesis_ready,
        "synthesis_must_disclose_partial": partial or bool(
            execute_body.get("synthesisMustDisclosePartial")
        ),
    }
