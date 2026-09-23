"""Layer 103: enforce answer provenance on save and recovery paths.

New Layer 103 chat answers declare an answer-provenance protocol. Removing or
corrupting the provenance receipt cannot downgrade such an answer to legacy.
Older answers remain readable, while Layer 102 receipts are still verified when
present.
"""

from __future__ import annotations

from core.cognition.answer_provenance import verify_answer_provenance
from core.cognition.delivery_integrity import verify_chat_delivery_payload


VERSION = "layer103-recovery-provenance-1"
PROTOCOL_KEY = "answer_provenance_protocol"
PROTOCOL_VERSION = "1.0"


def mark_answer_provenance_required(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise TypeError("answer_provenance_payload_must_be_object")
    marked = dict(payload)
    marked[PROTOCOL_KEY] = PROTOCOL_VERSION
    return marked


def verify_recovered_answer_payload(
    payload: dict | None,
    *,
    expected_request_id: str | None = None,
) -> dict:
    delivery = verify_chat_delivery_payload(
        payload,
        expected_request_id=expected_request_id,
    )
    if not delivery.get("valid"):
        return {
            "version": VERSION,
            "valid": False,
            "status": "invalid_delivery",
            "provenance_required": False,
            "provenance_present": False,
            "delivery_integrity": delivery,
            "answer_provenance": {},
            "issues": ["recovery_delivery_integrity_invalid"],
        }

    body = payload if isinstance(payload, dict) else {}
    cognition = body.get("cognition")
    cognition = cognition if isinstance(cognition, dict) else {}
    receipt = cognition.get("answer_provenance")
    release = cognition.get("release_provenance")
    model = cognition.get("model_receipt")
    context_budget = cognition.get("context_budget")
    persistence = cognition.get("assistant_persistence")

    protocol_present = PROTOCOL_KEY in body
    protocol = body.get(PROTOCOL_KEY)
    provenance_present = isinstance(receipt, dict)
    issues: list[str] = []

    if protocol_present and protocol != PROTOCOL_VERSION:
        issues.append("answer_provenance_protocol_unsupported")
    if protocol_present and not provenance_present:
        issues.append("answer_provenance_required_but_missing")
    if receipt is not None and not provenance_present:
        issues.append("answer_provenance_malformed")

    provenance_check = {}
    if provenance_present:
        provenance_check = verify_answer_provenance(
            receipt,
            request_id=expected_request_id,
            final_reply=body.get("reply") if isinstance(body.get("reply"), str) else None,
            release_provenance=release if isinstance(release, dict) else {},
            model_receipt=model if isinstance(model, dict) else {},
            context_budget=context_budget if isinstance(context_budget, dict) else {},
            assistant_persistence=persistence if isinstance(persistence, dict) else {},
        )
        if not provenance_check.get("valid"):
            issues.append("answer_provenance_verification_failed")

    if issues:
        status = "invalid"
    elif protocol_present and provenance_check.get("verified_production"):
        status = "verified_production"
    elif protocol_present:
        status = "valid_unverified_runtime"
    elif provenance_present and provenance_check.get("verified_production"):
        status = "verified_layer102_compat"
    elif provenance_present:
        status = "valid_layer102_compat"
    else:
        status = "legacy_no_answer_provenance"

    return {
        "version": VERSION,
        "valid": not issues,
        "status": status,
        "provenance_required": protocol_present,
        "provenance_present": provenance_present,
        "delivery_integrity": delivery,
        "answer_provenance": provenance_check,
        "issues": issues,
    }


def require_recovered_answer_payload(
    payload: dict,
    *,
    expected_request_id: str | None = None,
) -> dict:
    check = verify_recovered_answer_payload(
        payload,
        expected_request_id=expected_request_id,
    )
    if not check.get("valid"):
        raise ValueError("chat_recovery_provenance_mismatch")
    return check
