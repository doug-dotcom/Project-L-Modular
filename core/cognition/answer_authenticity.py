"""Layer 104: server-secret authenticity for answer provenance.

Public hashes prove internal consistency, but an actor able to rewrite all stored
fields can also recompute public hashes. Layer 104 adds HMAC-SHA256 authenticity
using a server-only secret that is never included in saved payloads.
"""

from __future__ import annotations

from hashlib import sha256
import hmac
import json
import os
import re


VERSION = "layer104-answer-authenticity-1"
ALGORITHM = "HMAC-SHA256"
SIGNING_KEY_ENV = "L_ANSWER_PROVENANCE_SIGNING_KEY"
MIN_KEY_BYTES = 32


def _canonical_bytes(value: dict) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _resolve_key(signing_key: str | bytes | None = None) -> bytes:
    value = signing_key
    if value is None:
        value = os.getenv(SIGNING_KEY_ENV, "")
    if isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bytes):
        raw = value
    else:
        raw = b""
    return raw if len(raw) >= MIN_KEY_BYTES else b""


def authenticity_status(signing_key: str | bytes | None = None) -> dict:
    key = _resolve_key(signing_key)
    return {
        "version": VERSION,
        "algorithm": ALGORITHM,
        "configured": bool(key),
        "minimum_key_bytes": MIN_KEY_BYTES,
        "secret_exposed": False,
    }


def sign_answer_provenance(
    answer_provenance: dict | None,
    *,
    signing_key: str | bytes | None = None,
) -> dict:
    provenance = dict(answer_provenance or {})
    key = _resolve_key(signing_key)
    provenance_receipt_sha = str(
        provenance.get("receipt_sha256") or ""
    ).strip()
    payload_sha = sha256(_canonical_bytes(provenance)).hexdigest()

    if not key or not re.fullmatch(r"[0-9a-f]{64}", provenance_receipt_sha):
        return {
            "version": VERSION,
            "algorithm": ALGORITHM,
            "status": "unavailable",
            "valid": False,
            "answer_provenance_receipt_sha256": provenance_receipt_sha,
            "signed_payload_sha256": payload_sha,
            "signature": "",
            "issues": [
                "signing_key_unavailable"
                if not key
                else "answer_provenance_receipt_invalid"
            ],
        }

    signature = hmac.new(
        key,
        _canonical_bytes(provenance),
        sha256,
    ).hexdigest()
    return {
        "version": VERSION,
        "algorithm": ALGORITHM,
        "status": "signed",
        "valid": True,
        "answer_provenance_receipt_sha256": provenance_receipt_sha,
        "signed_payload_sha256": payload_sha,
        "signature": signature,
        "issues": [],
    }


def verify_answer_authenticity(
    authenticity: dict | None,
    answer_provenance: dict | None,
    *,
    signing_key: str | bytes | None = None,
) -> dict:
    if not isinstance(authenticity, dict):
        return {
            "version": VERSION,
            "valid": False,
            "authentic": False,
            "issues": ["answer_authenticity_missing_or_malformed"],
        }

    provenance = dict(answer_provenance or {})
    key = _resolve_key(signing_key)
    issues: list[str] = []

    if authenticity.get("version") != VERSION:
        issues.append("answer_authenticity_version_invalid")
    if authenticity.get("algorithm") != ALGORITHM:
        issues.append("answer_authenticity_algorithm_invalid")
    if authenticity.get("status") != "signed" or authenticity.get("valid") is not True:
        issues.append("answer_authenticity_not_signed")
    if not key:
        issues.append("answer_authenticity_signing_key_unavailable")

    provenance_receipt_sha = str(
        provenance.get("receipt_sha256") or ""
    ).strip()
    if str(authenticity.get("answer_provenance_receipt_sha256") or "") != provenance_receipt_sha:
        issues.append("answer_authenticity_provenance_receipt_mismatch")

    payload_sha = sha256(_canonical_bytes(provenance)).hexdigest()
    if str(authenticity.get("signed_payload_sha256") or "") != payload_sha:
        issues.append("answer_authenticity_payload_hash_mismatch")

    declared_signature = str(authenticity.get("signature") or "").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", declared_signature):
        issues.append("answer_authenticity_signature_invalid")
    elif key:
        expected = hmac.new(
            key,
            _canonical_bytes(provenance),
            sha256,
        ).hexdigest()
        if not hmac.compare_digest(declared_signature, expected):
            issues.append("answer_authenticity_signature_mismatch")

    return {
        "version": VERSION,
        "valid": not issues,
        "authentic": not issues,
        "algorithm": ALGORITHM,
        "issues": issues,
        "answer_provenance_receipt_sha256": provenance_receipt_sha,
        "signed_payload_sha256": payload_sha if not issues else "",
    }
