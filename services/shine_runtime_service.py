"""Bounded human-facing Shine runtime preflight.

This service is read-only. It asks Concierge to preview the request and asks
Defence for the exact reviewed snapshots relevant to the human-facing runtime.
It never executes specialists, writes memory or carries credentials into the
durable task receipt.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable
from uuid import UUID

import httpx


def _uuid(value: Any) -> str:
    return str(UUID(str(value)))


def _safe_object(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _post_json(
    post: Callable[..., Any],
    url: str,
    *,
    authorization: str,
    apikey: str,
    payload: dict,
    timeout_seconds: float,
) -> tuple[int, dict]:
    headers = {
        "Authorization": authorization,
        "Content-Type": "application/json",
    }
    if apikey:
        headers["apikey"] = apikey
    response = post(
        url,
        json=payload,
        headers=headers,
        timeout=timeout_seconds,
        follow_redirects=False,
    )
    try:
        data = response.json()
    except Exception:
        data = {}
    return int(getattr(response, "status_code", 500)), _safe_object(data)


def _concierge_receipt(data: dict) -> dict:
    route = _safe_object(data.get("route"))
    foundation = _safe_object(data.get("foundation"))
    plan = _safe_object(data.get("plan"))
    selected = route.get("selectedRoutes")
    candidates = route.get("candidates")
    routed = foundation.get("routedCapabilities")
    steps = plan.get("steps")
    return {
        "status": "ready" if data.get("preview") is True else "unavailable",
        "preview": data.get("preview") is True,
        "persisted": data.get("persisted") is True,
        "resolver_version": route.get("resolverVersion"),
        "mode": route.get("mode"),
        "intent_key": route.get("intentKey"),
        "confidence": route.get("confidence"),
        "reason": route.get("reason"),
        "selected_routes": selected if isinstance(selected, list) else [],
        "candidate_count": len(candidates) if isinstance(candidates, list) else 0,
        "plan": {
            "version": plan.get("version"),
            "orchestration": plan.get("orchestration"),
            "confirmation_policy": plan.get("confirmationPolicy"),
            "steps": steps if isinstance(steps, list) else [],
        },
        "foundation": {
            "protocol": foundation.get("protocol"),
            "requires_bridge": foundation.get("requiresFoundationBridge") is True,
            "routed_capabilities": routed if isinstance(routed, list) else [],
        },
        "boundaries": {
            "specialist_execution_performed": False,
            "concierge_tasks_created": False,
            "memory_mutation_performed": False,
        },
    }


def _defence_receipt(data: dict) -> dict:
    result = _safe_object(data.get("result"))
    reviews = result.get("reviews")
    clean_reviews = []
    if isinstance(reviews, list):
        for review in reviews:
            item = _safe_object(review)
            clean_reviews.append(
                {
                    "app_id": item.get("appId"),
                    "repo": item.get("repo"),
                    "review_commit_sha": item.get("reviewCommitSha"),
                    "profile_version": item.get("profileVersion"),
                    "policies": item.get("policies")
                    if isinstance(item.get("policies"), list)
                    else [],
                    "status": item.get("status"),
                    "limitation": item.get("limitation"),
                }
            )
    return {
        "status": (
            "ready"
            if data.get("status") == "completed" and clean_reviews
            else "unavailable"
        ),
        "review_count": len(clean_reviews),
        "reviews": clean_reviews,
        "snapshot_only": True,
        "current_head_certification_implied": False,
    }


def build_shine_runtime_preflight(
    *,
    supabase_url: str,
    publishable_key: str,
    authorization: str,
    user_id: str,
    message: str,
    conversation_id: str,
    request_id: str,
    timeout_seconds: float = 3.0,
    post_impl: Callable[..., Any] | None = None,
) -> dict:
    """Return a credential-free Concierge + Defence receipt for one user turn."""
    owner_id = _uuid(user_id)
    req_id = _uuid(request_id)
    if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
        return {
            "version": "shine-human-runtime-preflight-v1",
            "status": "degraded",
            "reason": "authenticated_user_transport_unavailable",
            "concierge": {"status": "unavailable"},
            "defence": {"status": "unavailable"},
        }

    base = str(supabase_url or "").rstrip("/")
    if not base.startswith("https://"):
        return {
            "version": "shine-human-runtime-preflight-v1",
            "status": "degraded",
            "reason": "runtime_service_url_unavailable",
            "concierge": {"status": "unavailable"},
            "defence": {"status": "unavailable"},
        }

    post = post_impl or httpx.post
    concierge_payload = {
        "message": str(message),
        "sourceConversationId": str(conversation_id or "doug_primary")[:180],
        "sourceMessageId": req_id,
        "idempotencyKey": ("shine-preview:" + req_id)[:128],
        "preview": True,
        "metadata": {
            "surface": "shine",
            "sourceSystem": "project-l",
            "preflightVersion": "1.0",
        },
    }
    defence_payload = {
        "protocol": "shine-concierge/companion-v1",
        "schemaVersion": "1.0.0",
        "operation": "execute",
        "requestId": req_id,
        "userScope": {"userId": owner_id},
        "idempotencyKey": ("shine-defence:" + req_id)[:180],
        "capability": "defence_status",
        "payload": {
            "query": "project-l shine-ai",
        },
    }

    calls = {
        "concierge": (
            base + "/functions/v1/concierge-intake",
            concierge_payload,
        ),
        "defence": (
            base + "/functions/v1/defence-companion",
            defence_payload,
        ),
    }

    outcomes: dict[str, tuple[int, dict] | Exception] = {}
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="shine-preflight") as pool:
        futures = {
            name: pool.submit(
                _post_json,
                post,
                url,
                authorization=authorization,
                apikey=publishable_key,
                payload=payload,
                timeout_seconds=timeout_seconds,
            )
            for name, (url, payload) in calls.items()
        }
        for name, future in futures.items():
            try:
                outcomes[name] = future.result()
            except Exception as exc:
                outcomes[name] = exc

    concierge = {"status": "unavailable"}
    defence = {"status": "unavailable"}

    concierge_outcome = outcomes.get("concierge")
    if isinstance(concierge_outcome, tuple) and concierge_outcome[0] == 200:
        concierge = _concierge_receipt(concierge_outcome[1])

    defence_outcome = outcomes.get("defence")
    if isinstance(defence_outcome, tuple) and defence_outcome[0] == 200:
        defence = _defence_receipt(defence_outcome[1])

    ready = concierge.get("status") == "ready" and defence.get("status") == "ready"
    return {
        "version": "shine-human-runtime-preflight-v1",
        "status": "ready" if ready else "degraded",
        "request_id": req_id,
        "components": {
            "foundation": "capability-truth-via-concierge",
            "project_l": "identity-memory-cognition-owner",
            "shine_ai": "model-inference-runtime",
            "concierge": "request-planning-preview",
            "defence": "review-snapshot-evidence",
        },
        "concierge": concierge,
        "defence": defence,
        "boundaries": {
            "preflight_is_read_only": True,
            "preflight_is_not_specialist_execution": True,
            "defence_snapshot_is_not_current_head_certification": True,
            "project_l_remains_user_voice": True,
        },
    }


__all__ = ["build_shine_runtime_preflight"]
