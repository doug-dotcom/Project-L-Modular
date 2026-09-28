"""Human-facing Shine convergence preflight.

This service is deliberately read/preview oriented. It lets the authenticated L
front door ask Concierge how it would route the request and attach current
Defence review evidence without creating Concierge jobs or moving memory
ownership away from Project L.
"""

from __future__ import annotations

from typing import Any

import httpx


MAX_RESPONSE_BYTES = 128 * 1024


def _origin(value: str) -> str:
    origin = str(value or "").rstrip("/")
    if not origin.startswith("https://"):
        raise RuntimeError("shine-convergence-supabase-url-invalid")
    return origin


def _json(response) -> dict:
    raw = bytes(getattr(response, "content", b""))
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError("shine-convergence-response-too-large")
    try:
        payload = response.json()
    except Exception as exc:
        raise RuntimeError("shine-convergence-response-invalid") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("shine-convergence-response-invalid")
    return payload


def _post(
    *,
    url: str,
    authorization: str,
    body: dict,
    idempotency_key: str | None = None,
    timeout_seconds: float = 8.0,
    post_impl=None,
) -> tuple[int, dict]:
    post = post_impl or httpx.post
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    response = post(
        url,
        headers=headers,
        json=body,
        timeout=timeout_seconds,
        follow_redirects=False,
    )
    return int(response.status_code), _json(response)


def build_shine_convergence_preflight(
    *,
    supabase_url: str,
    authorization: str,
    user_id: str,
    request_id: str,
    message: str,
    conversation_id: str | None,
    foundation_status: dict | None = None,
    timeout_seconds: float = 8.0,
    post_impl=None,
) -> dict:
    """Return a bounded front-door receipt; failures degrade visibly, never silently."""
    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        return {
            "version": "1.0",
            "status": "unavailable",
            "reason": "authenticated-user-token-missing",
            "concierge": {"status": "unavailable"},
            "defence": {"status": "unavailable"},
            "foundation": foundation_status or {"status": "unknown"},
        }

    origin = _origin(supabase_url)
    source_conversation = str(conversation_id or "doug_primary")[:180]
    idempotency = ("preview:" + request_id)[:128]

    concierge: dict[str, Any]
    try:
        status, payload = _post(
            url=origin + "/functions/v1/concierge-intake",
            authorization=authorization,
            idempotency_key=idempotency,
            timeout_seconds=timeout_seconds,
            post_impl=post_impl,
            body={
                "preview": True,
                "message": message,
                "sourceConversationId": source_conversation,
                "sourceMessageId": request_id,
                "idempotencyKey": idempotency,
                "metadata": {
                    "sourceSurface": "shine-human-runtime",
                    "durableRequestId": request_id,
                },
            },
        )
        if status == 200 and payload.get("preview") is True:
            concierge = {
                "status": "ready",
                "previewOnly": True,
                "persisted": payload.get("persisted") is True,
                "route": payload.get("route"),
                "plan": payload.get("plan"),
                "foundation": payload.get("foundation"),
                "boundaries": payload.get("boundaries"),
            }
        else:
            concierge = {
                "status": "unavailable",
                "httpStatus": status,
                "reason": str(payload.get("error") or "preview-failed"),
            }
    except Exception as exc:
        concierge = {
            "status": "unavailable",
            "reason": type(exc).__name__,
        }

    defence: dict[str, Any]
    try:
        status, payload = _post(
            url=origin + "/functions/v1/defence-companion",
            authorization=authorization,
            timeout_seconds=timeout_seconds,
            post_impl=post_impl,
            body={
                "protocol": "shine-concierge/companion-v1",
                "schemaVersion": "1.0.0",
                "operation": "execute",
                "requestId": request_id,
                "userScope": {"userId": user_id},
                "idempotencyKey": ("human-runtime-defence:" + request_id)[:180],
                "capability": "defence_status",
                "payload": {
                    "query": "project-l shine-ai",
                },
            },
        )
        result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        if status == 200 and payload.get("status") == "completed":
            reviews = result.get("reviews") if isinstance(result.get("reviews"), list) else []
            defence = {
                "status": "ready",
                "summary": result.get("summary"),
                "reviewCount": len(reviews),
                "reviews": [
                    {
                        "appId": row.get("appId"),
                        "reviewCommitSha": row.get("reviewCommitSha"),
                        "profileVersion": row.get("profileVersion"),
                        "policies": row.get("policies"),
                        "status": row.get("status"),
                        "limitation": row.get("limitation"),
                    }
                    for row in reviews
                    if isinstance(row, dict)
                ],
                "boundaries": result.get("boundaries"),
            }
        else:
            defence = {
                "status": "unavailable",
                "httpStatus": status,
                "reason": str(payload.get("error") or payload.get("status") or "review-failed"),
            }
    except Exception as exc:
        defence = {
            "status": "unavailable",
            "reason": type(exc).__name__,
        }

    components = {
        "foundation": foundation_status or {
            "status": (
                "referenced-by-concierge"
                if isinstance(concierge.get("foundation"), dict)
                else "unknown"
            ),
            "routing": concierge.get("foundation"),
        },
        "projectL": {
            "status": "owner",
            "ownsIdentity": True,
            "ownsMemory": True,
            "ownsCognition": True,
            "ownsUserVoice": True,
        },
        "shineAI": {
            "status": "model-runtime-target",
            "directMemoryAuthority": False,
            "directToolAuthorityFromCompanion": False,
        },
        "concierge": concierge,
        "defence": defence,
    }

    ready = (
        concierge.get("status") == "ready"
        and defence.get("status") == "ready"
    )
    return {
        "version": "1.0",
        "status": "ready" if ready else "degraded",
        "requestId": request_id,
        "components": components,
        "boundaries": {
            "singleHumanFrontDoor": True,
            "conciergePreviewOnly": True,
            "specialistExecutionPerformedByPreflight": False,
            "memoryMutationPerformedByPreflight": False,
            "projectLOwnsMemory": True,
            "projectLOwnsVoice": True,
            "shineAIOwnsModelRuntime": True,
        },
    }


__all__ = ["build_shine_convergence_preflight"]
