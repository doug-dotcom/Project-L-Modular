"""Authenticated, read-only Shine-Me context request boundary."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from core.cognition.shine_me import build_shine_me_from_cognition


OWNER_SCOPES = frozenset({
    "general", "identity", "episodic", "sport", "family", "recovery",
    "health", "project_l",
})


def prepare_shine_me_context(
    *,
    query: str,
    verified_account: Mapping[str, object] | None,
    configured_owner_id: str,
    retrieve: Callable[[str], dict],
    cognize: Callable[[str, dict], dict],
) -> dict:
    """Retrieve and publish one gated memory for the verified owner only.

    The account must be supplied by the server's authentication middleware.
    Callers must not pass a user ID from the request body or model output.
    """
    owner_id = str(configured_owner_id or "").strip()
    if not owner_id:
        raise RuntimeError("Shine-Me owner binding is not configured")
    user_id = str((verified_account or {}).get("user_id") or "").strip()
    if not user_id or user_id != owner_id:
        raise PermissionError("Shine-Me account does not own this memory")
    query = str(query or "").strip()
    if not 1 <= len(query) <= 2000:
        raise ValueError("Query must be between 1 and 2000 characters")

    rhee = retrieve(query)
    if not isinstance(rhee, dict):
        raise RuntimeError("Memory retrieval is unavailable")
    recall_plan = rhee.get("recall_plan") or {}
    temporal = rhee.get("temporal_memory") or {}
    if not isinstance(recall_plan, dict) or not isinstance(temporal, dict):
        raise RuntimeError("Memory retrieval status is invalid")
    if recall_plan.get("status") in {"unavailable", "needs_clarification", "budget_exceeded"}:
        raise RuntimeError("Memory retrieval did not complete")
    if temporal.get("status") in {"unavailable", "needs_clarification"}:
        raise RuntimeError("Memory freshness check did not complete")
    cognition = cognize(query, rhee)
    if not isinstance(cognition, dict):
        raise RuntimeError("Memory approval is unavailable")
    return build_shine_me_from_cognition(
        verified_user_id=user_id,
        retrieval_owner_id=owner_id,
        rhee_packet=rhee,
        cognitive_packet=cognition,
        allowed_scopes=OWNER_SCOPES,
    )
