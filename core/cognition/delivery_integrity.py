"""Layer 87 — delivery payload binding.

Bind the final chat payload to the exact reply and request identity before it is
cached or durably persisted, then verify the same receipt when a saved answer is
recovered. Receipts are privacy-safe: they contain hashes and delivery metadata,
not reply/evidence text.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any


DELIVERY_RECEIPT_KEY = "delivery_receipt"


def _canonical_sha256(value: Any) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _receipt_hash_from(payload: dict, *path: str) -> str:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict):
            return ""
        value = value.get(key)
    if not isinstance(value, dict):
        return ""
    return str(value.get("receipt_sha256") or "").strip()


def seal_chat_delivery_payload(
    payload: dict,
    *,
    request_id: str = "",
) -> dict:
    """Return a copy of *payload* with a self-hashed delivery receipt."""
    if not isinstance(payload, dict):
        raise TypeError("chat_delivery_payload_must_be_object")

    sealed = dict(payload)
    sealed.pop(DELIVERY_RECEIPT_KEY, None)
    reply = sealed.get("reply")
    if not isinstance(reply, str):
        raise TypeError("chat_delivery_reply_must_be_text")

    receipt = {
        "version": "1.0",
        "status": "sealed",
        "request_id": str(request_id or ""),
        "reply_sha256": sha256(reply.encode("utf-8")).hexdigest(),
        "payload_sha256": _canonical_sha256(sealed),
        "final_publication_receipt_sha256": _receipt_hash_from(
            sealed,
            "cognition",
            "evidence_evaluation",
            "final_publication",
        ),
        "assistant_persistence_receipt_sha256": _receipt_hash_from(
            sealed,
            "cognition",
            "assistant_persistence",
        ),
    }
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    sealed[DELIVERY_RECEIPT_KEY] = receipt
    return sealed


def verify_chat_delivery_payload(
    payload: dict | None,
    *,
    expected_request_id: str | None = None,
) -> dict:
    """Verify a sealed delivery payload without exposing reply text."""
    payload = dict(payload or {})
    issues: list[str] = []
    receipt = payload.get(DELIVERY_RECEIPT_KEY)

    if not isinstance(receipt, dict):
        return {
            "version": "1.0",
            "status": "legacy_unbound",
            "valid": True,
            "bound": False,
            "issues": [],
        }

    receipt_payload = dict(receipt)
    declared_receipt_sha = str(
        receipt_payload.pop("receipt_sha256", "") or ""
    ).strip()
    if declared_receipt_sha != _canonical_sha256(receipt_payload):
        issues.append("delivery_receipt_hash_mismatch")

    body = dict(payload)
    body.pop(DELIVERY_RECEIPT_KEY, None)
    actual_payload_sha = _canonical_sha256(body)
    if str(receipt.get("payload_sha256") or "") != actual_payload_sha:
        issues.append("delivery_payload_hash_mismatch")

    reply = body.get("reply")
    if not isinstance(reply, str):
        issues.append("delivery_reply_missing")
        actual_reply_sha = ""
    else:
        actual_reply_sha = sha256(reply.encode("utf-8")).hexdigest()
        if str(receipt.get("reply_sha256") or "") != actual_reply_sha:
            issues.append("delivery_reply_hash_mismatch")

    if expected_request_id is not None:
        if str(receipt.get("request_id") or "") != str(expected_request_id or ""):
            issues.append("delivery_request_id_mismatch")

    expected_publication = _receipt_hash_from(
        body,
        "cognition",
        "evidence_evaluation",
        "final_publication",
    )
    if (
        str(receipt.get("final_publication_receipt_sha256") or "")
        != expected_publication
    ):
        issues.append("delivery_publication_receipt_mismatch")

    expected_persistence = _receipt_hash_from(
        body,
        "cognition",
        "assistant_persistence",
    )
    if (
        str(receipt.get("assistant_persistence_receipt_sha256") or "")
        != expected_persistence
    ):
        issues.append("delivery_persistence_receipt_mismatch")

    return {
        "version": "1.0",
        "status": "verified" if not issues else "mismatch",
        "valid": not issues,
        "bound": True,
        "issues": issues,
        "request_id": str(receipt.get("request_id") or ""),
        "reply_sha256": actual_reply_sha,
        "payload_sha256": actual_payload_sha,
        "receipt_sha256": declared_receipt_sha,
    }


def require_chat_delivery_payload(
    payload: dict,
    *,
    expected_request_id: str | None = None,
) -> dict:
    """Raise when a payload claims delivery binding but does not verify."""
    result = verify_chat_delivery_payload(
        payload,
        expected_request_id=expected_request_id,
    )
    if result.get("bound") and not result.get("valid"):
        raise ValueError("chat_delivery_integrity_mismatch")
    return result
