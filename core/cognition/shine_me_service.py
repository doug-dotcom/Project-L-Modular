"""Authenticated, read-only Shine-Me context request boundary."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from core.cognition.shine_me import build_shine_me_from_cognition


OWNER_SCOPES = frozenset({
    "general", "identity", "episodic", "sport", "family", "recovery",
    "health", "project_l",
})


def shine_me_binding_status(
    *, verified_account: Mapping[str, object] | None,
    configured_owner_id: str,
    configured_memory_owner_id: str,
) -> dict[str, str]:
    """Report only the owner binding; this does not probe database availability."""
    owner_id = str(configured_owner_id or "").strip()
    if not owner_id:
        raise RuntimeError("Shine-Me owner binding is not configured")
    user_id = str((verified_account or {}).get("user_id") or "").strip()
    if not user_id or user_id != owner_id:
        raise PermissionError("Shine-Me account does not own this memory")
    memory_owner_id = str(configured_memory_owner_id or "").strip()
    if not memory_owner_id or memory_owner_id != owner_id:
        return {"status": "unavailable", "reason": "memory_owner_binding"}
    return {"status": "binding_ready", "reason": "owner_ids_match"}


def prepare_shine_me_context(
    *,
    query: str,
    verified_account: Mapping[str, object] | None,
    configured_owner_id: str,
    configured_memory_owner_id: str,
    retrieve: Callable[[str], dict],
    cognize: Callable[[str, dict], dict],
) -> dict:
    """Retrieve and publish one gated memory for the verified owner only.

    The account must be supplied by the server's authentication middleware.
    Callers must not pass a user ID from the request body or model output.
    """
    binding = shine_me_binding_status(
        verified_account=verified_account,
        configured_owner_id=configured_owner_id,
        configured_memory_owner_id=configured_memory_owner_id,
    )
    if binding["status"] != "binding_ready":
        raise RuntimeError("Shine-Me memory namespace is not bound to its owner")
    owner_id = str(configured_owner_id).strip()
    user_id = owner_id
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
    if recall_plan.get("status") != "checked":
        raise RuntimeError("Memory retrieval did not complete")
    if temporal.get("status") != "checked":
        raise RuntimeError("Memory freshness check did not complete")
    if str(temporal.get("user_id") or "").strip() != owner_id:
        raise PermissionError("Memory snapshot belongs to a different owner")
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


def answer_from_shine_me_context(context: Mapping[str, object]) -> dict:
    """Give an inspectable first answer without inventing details or invoking a model."""
    records = context.get("records")
    if not isinstance(records, list) or not records:
        return {
            "status": "no_approved_evidence",
            "reply": "I couldn't verify a relevant memory for that question yet.",
            "evidence": [],
        }

    record = records[0]
    if not isinstance(record, dict):
        raise RuntimeError("Shine-Me evidence is malformed")
    text = str(record.get("text") or "").strip()
    source = str(record.get("source") or "").strip()
    provenance = str(record.get("provenance") or "")
    if not text or not source:
        raise RuntimeError("Shine-Me evidence is incomplete")

    if provenance == "user_statement":
        reply = f"I found this in something you said: “{text}”"
        status = "quoted_user_memory"
    elif provenance == "model_statement":
        reply = f"An earlier assistant wrote: “{text}” I can't verify that as something you said."
        status = "unverified_model_memory"
    else:
        reply = f"I found this record: “{text}” Its original author isn't verified."
        status = "unverified_source_memory"

    return {
        "status": status,
        "reply": reply,
        "evidence": [{"source": source, "provenance": provenance}],
    }
