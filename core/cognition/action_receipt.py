"""Request-bound receipts for connected external actions.

Receipts are compact audit records. They never authorise an action; the action
boundary is still protected by the durable-task checkpoint. A receipt records
what the provider confirmed after that boundary and is later covered by the
sealed chat delivery payload.
"""
import hashlib
import json
import re


VERSION = "layer165-connected-action-receipt-1"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(value):
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def build_action_receipt(*, request_id, capability, action, resource_id, subject):
    request_id = str(request_id or "")
    body = {
        "version": VERSION,
        "status": "confirmed",
        "request_id": request_id,
        "request_bound": bool(request_id),
        "capability": str(capability or ""),
        "action": str(action or ""),
        "resource_id": str(resource_id or ""),
        "subject_sha256": _sha256_text(subject),
    }
    body["receipt_sha256"] = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
    return body


def verify_action_receipt(receipt, *, expected_request_id=None):
    issues = []
    if not isinstance(receipt, dict):
        return {
            "version": VERSION,
            "valid": False,
            "status": "mismatch",
            "issues": ["action_receipt_missing_or_malformed"],
        }

    required = {
        "version", "status", "request_id", "request_bound", "capability",
        "action", "resource_id", "subject_sha256", "receipt_sha256",
    }
    if set(receipt) != required:
        issues.append("action_receipt_schema_mismatch")
    if receipt.get("version") != VERSION:
        issues.append("action_receipt_version_mismatch")
    if receipt.get("status") != "confirmed":
        issues.append("action_receipt_status_invalid")
    if not isinstance(receipt.get("request_bound"), bool):
        issues.append("action_receipt_request_bound_invalid")

    request_id = receipt.get("request_id")
    if not isinstance(request_id, str):
        issues.append("action_receipt_request_id_invalid")
    elif bool(request_id) != bool(receipt.get("request_bound")):
        issues.append("action_receipt_binding_flag_mismatch")
    if expected_request_id is not None and request_id != str(expected_request_id):
        issues.append("action_receipt_request_id_mismatch")

    for field in ("capability", "action", "resource_id"):
        if not isinstance(receipt.get(field), str) or not receipt.get(field):
            issues.append(f"action_receipt_{field}_invalid")
    for field in ("subject_sha256", "receipt_sha256"):
        if re.fullmatch(r"[0-9a-f]{64}", str(receipt.get(field) or "")) is None:
            issues.append(f"action_receipt_{field}_invalid")

    if not issues:
        body = dict(receipt)
        supplied = body.pop("receipt_sha256")
        expected = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
        if supplied != expected:
            issues.append("action_receipt_hash_mismatch")

    return {
        "version": VERSION,
        "valid": not issues,
        "status": "verified" if not issues else "mismatch",
        "request_bound": bool(receipt.get("request_bound")),
        "issues": issues,
    }


def verify_payload_action_receipt(payload, *, expected_request_id):
    if not isinstance(payload, dict):
        return {
            "version": VERSION,
            "valid": False,
            "status": "mismatch",
            "present": False,
            "issues": ["action_payload_missing_or_malformed"],
        }
    route = payload.get("route")
    receipt = route.get("action_receipt") if isinstance(route, dict) else None
    if receipt is None:
        return {
            "version": VERSION,
            "valid": True,
            "status": "not_present",
            "present": False,
            "request_bound": False,
            "issues": [],
        }
    check = verify_action_receipt(
        receipt,
        expected_request_id=expected_request_id,
    )
    return {
        **check,
        "present": True,
    }


def require_payload_action_receipt(payload, *, expected_request_id):
    check = verify_payload_action_receipt(
        payload,
        expected_request_id=expected_request_id,
    )
    if not check.get("valid"):
        raise ValueError("connected_action_receipt_mismatch")
    return check
