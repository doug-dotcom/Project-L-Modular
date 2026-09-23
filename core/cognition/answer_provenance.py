"""Layer 102: bind each saved answer to the exact runtime release provenance.

The receipt stores hashes and release identity only. It never duplicates answer text,
prompts, evidence, credentials, or model payloads.
"""

from __future__ import annotations

from hashlib import sha256
import json
import re

from core.cognition.release_provenance import verify_release_provenance


VERSION = "layer102-answer-provenance-1"
RELEASE_LAYER = 102


def _canonical_sha256(value: dict) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _hash_object(value: object) -> str:
    return _canonical_sha256(value) if isinstance(value, dict) else ""


def build_answer_provenance(
    *,
    request_id: str,
    final_reply: str,
    release_provenance: dict | None,
    model_receipt: dict | None,
    context_budget: dict | None,
    assistant_persistence: dict | None,
    release_layer: int = RELEASE_LAYER,
) -> dict:
    release = dict(release_provenance or {})
    release_check = verify_release_provenance(release)
    production_verified = bool(
        release_check.get("valid")
        and release_check.get("verified_production")
    )
    commit_sha = str(release.get("commit_sha") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        commit_sha = ""

    receipt = {
        "version": VERSION,
        "status": "verified_production" if production_verified else "runtime_unverified",
        "verified": production_verified,
        "release_layer": int(release_layer),
        "request_id": str(request_id or ""),
        "reply_sha256": sha256(str(final_reply or "").encode("utf-8")).hexdigest(),
        "release_commit_sha": commit_sha,
        "release_provenance_receipt_sha256": str(
            release.get("receipt_sha256") or ""
        ).strip(),
        "response_model_receipt_sha256": _hash_object(model_receipt),
        "context_budget_receipt_sha256": _hash_object(context_budget),
        "assistant_persistence_receipt_sha256": _hash_object(
            assistant_persistence
        ),
        "claims": {
            "answer_bound_to_reported_release": (
                "verified" if production_verified else "not_verified"
            ),
            "answer_quality": "not_asserted",
            "memory_quality": "not_asserted",
            "human_acceptance": "not_asserted",
        },
    }
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    return receipt


def verify_answer_provenance(
    receipt: dict | None,
    *,
    request_id: str | None = None,
    final_reply: str | None = None,
    release_provenance: dict | None = None,
    model_receipt: dict | None = None,
    context_budget: dict | None = None,
    assistant_persistence: dict | None = None,
) -> dict:
    if not isinstance(receipt, dict):
        return {
            "version": VERSION,
            "valid": False,
            "verified_production": False,
            "issues": ["answer_provenance_missing_or_malformed"],
        }

    payload = dict(receipt)
    declared = str(payload.pop("receipt_sha256", "") or "").strip()
    issues: list[str] = []

    if not re.fullmatch(r"[0-9a-f]{64}", declared):
        issues.append("answer_provenance_receipt_hash_invalid")
    elif declared != _canonical_sha256(payload):
        issues.append("answer_provenance_receipt_hash_mismatch")

    if str(receipt.get("version") or "") != VERSION:
        issues.append("answer_provenance_version_invalid")

    layer = receipt.get("release_layer")
    if type(layer) is not int or layer < RELEASE_LAYER:
        issues.append("answer_provenance_release_layer_invalid")

    reply_sha = str(receipt.get("reply_sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", reply_sha):
        issues.append("answer_provenance_reply_hash_invalid")
    elif final_reply is not None:
        expected_reply_sha = sha256(str(final_reply).encode("utf-8")).hexdigest()
        if reply_sha != expected_reply_sha:
            issues.append("answer_provenance_reply_hash_mismatch")

    if request_id is not None and str(receipt.get("request_id") or "") != str(request_id):
        issues.append("answer_provenance_request_id_mismatch")

    release_check = None
    if release_provenance is not None:
        release_check = verify_release_provenance(release_provenance)
        release_receipt_sha = str(
            (release_provenance or {}).get("receipt_sha256") or ""
        ).strip()
        if str(receipt.get("release_provenance_receipt_sha256") or "") != release_receipt_sha:
            issues.append("answer_provenance_release_receipt_mismatch")
        release_commit = str(
            (release_provenance or {}).get("commit_sha") or ""
        ).strip().lower()
        if str(receipt.get("release_commit_sha") or "") != release_commit:
            issues.append("answer_provenance_release_commit_mismatch")
        if not release_check.get("valid"):
            issues.append("answer_provenance_release_receipt_invalid")

    bindings = (
        ("response_model_receipt_sha256", model_receipt),
        ("context_budget_receipt_sha256", context_budget),
        ("assistant_persistence_receipt_sha256", assistant_persistence),
    )
    for field, value in bindings:
        if value is None:
            continue
        if str(receipt.get(field) or "") != _hash_object(value):
            issues.append(field.replace("_sha256", "_mismatch"))

    verified_claim = receipt.get("verified") is True
    if verified_claim:
        if receipt.get("status") != "verified_production":
            issues.append("answer_provenance_verified_status_mismatch")
        if release_check is not None and not release_check.get("verified_production"):
            issues.append("answer_provenance_release_not_verified_production")
        if not re.fullmatch(
            r"[0-9a-f]{40}",
            str(receipt.get("release_commit_sha") or ""),
        ):
            issues.append("answer_provenance_commit_missing")

    valid = not issues
    verified_production = bool(valid and verified_claim)
    return {
        "version": VERSION,
        "valid": valid,
        "verified_production": verified_production,
        "issues": issues,
        "release_layer": layer if type(layer) is int else None,
        "release_commit_sha": (
            str(receipt.get("release_commit_sha") or "")
            if valid
            else ""
        ),
        "receipt_sha256": declared,
    }
