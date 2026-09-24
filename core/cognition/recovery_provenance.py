"""Layer 103: enforce answer provenance on save and recovery paths.

New Layer 103 chat answers declare an answer-provenance protocol. Removing or
corrupting the provenance receipt cannot downgrade such an answer to legacy.
Older answers remain readable, while Layer 102 receipts are still verified when
present.
"""

from __future__ import annotations

from core.cognition.answer_provenance import verify_answer_provenance
from core.cognition.answer_authenticity import verify_answer_authenticity
from core.cognition.delivery_integrity import verify_chat_delivery_payload


VERSION = "layer104-recovery-authenticity-1"
PROTOCOL_KEY = "answer_provenance_protocol"
LEGACY_PROTOCOL_VERSION = "1.0"
PROTOCOL_VERSION = "2.0"
SUPPORTED_PROTOCOLS = {LEGACY_PROTOCOL_VERSION, PROTOCOL_VERSION}


def mark_answer_provenance_required(
    payload: dict,
    *,
    protocol_version: str = PROTOCOL_VERSION,
) -> dict:
    if not isinstance(payload, dict):
        raise TypeError("answer_provenance_payload_must_be_object")
    if protocol_version not in SUPPORTED_PROTOCOLS:
        raise ValueError("answer_provenance_protocol_unsupported")
    marked = dict(payload)
    marked[PROTOCOL_KEY] = protocol_version
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

    authenticity = cognition.get("answer_authenticity")
    protocol_present = PROTOCOL_KEY in body
    protocol = body.get(PROTOCOL_KEY)
    provenance_present = isinstance(receipt, dict)
    authenticity_present = isinstance(authenticity, dict)
    issues: list[str] = []

    if protocol_present and (
        not isinstance(protocol, str) or protocol not in SUPPORTED_PROTOCOLS
    ):
        issues.append("answer_provenance_protocol_unsupported")
    if protocol_present and not provenance_present:
        issues.append("answer_provenance_required_but_missing")
    if receipt is not None and not provenance_present:
        issues.append("answer_provenance_malformed")
    if protocol == PROTOCOL_VERSION and not authenticity_present:
        issues.append("answer_authenticity_required_but_missing")
    if authenticity is not None and not authenticity_present:
        issues.append("answer_authenticity_malformed")

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

    authenticity_check = {}
    if authenticity_present:
        authenticity_check = verify_answer_authenticity(
            authenticity,
            receipt if isinstance(receipt, dict) else {},
        )
        if not authenticity_check.get("valid"):
            issues.append("answer_authenticity_verification_failed")

    if issues:
        status = "invalid"
    elif protocol == PROTOCOL_VERSION and provenance_check.get("verified_production"):
        status = "verified_authentic_production"
    elif protocol == PROTOCOL_VERSION:
        status = "valid_authentic_unverified_runtime"
    elif protocol == LEGACY_PROTOCOL_VERSION and provenance_check.get("verified_production"):
        status = "verified_production"
    elif protocol == LEGACY_PROTOCOL_VERSION:
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
        "authenticity_required": protocol == PROTOCOL_VERSION,
        "authenticity_present": authenticity_present,
        "delivery_integrity": delivery,
        "answer_provenance": provenance_check,
        "answer_authenticity": authenticity_check,
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
