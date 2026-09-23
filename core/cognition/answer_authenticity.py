"""Layer 105: rotatable keyring for server-authenticated answer provenance.

Layer 104 introduced HMAC authenticity with one server secret. Layer 105 adds
non-secret key identifiers and a bounded verification keyring so new signing
keys can be activated without invalidating historical signatures.
"""

from __future__ import annotations

from hashlib import sha256
import hmac
import json
import os
import re


LEGACY_VERSION = "layer104-answer-authenticity-1"
VERSION = "layer105-answer-authenticity-keyring-1"
ALGORITHM = "HMAC-SHA256"

# Layer 104 historical verification key. Retained during rotations.
SIGNING_KEY_ENV = "L_ANSWER_PROVENANCE_SIGNING_KEY"

ACTIVE_KEY_ID_ENV = "L_ANSWER_PROVENANCE_ACTIVE_KEY_ID"
VERIFY_KEY_IDS_ENV = "L_ANSWER_PROVENANCE_VERIFY_KEY_IDS"
KEY_ENV_PREFIX = "L_ANSWER_PROVENANCE_SIGNING_KEY_"
MIN_KEY_BYTES = 32
_KEY_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


def _canonical_bytes(value: dict) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _normalise_key(value: object) -> bytes:
    if isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bytes):
        raw = value
    else:
        raw = b""
    return raw if len(raw) >= MIN_KEY_BYTES else b""


def _resolve_legacy_key(
    signing_key: str | bytes | None = None,
    *,
    environ: dict | None = None,
) -> bytes:
    if signing_key is not None:
        return _normalise_key(signing_key)
    env = os.environ if environ is None else environ
    return _normalise_key(env.get(SIGNING_KEY_ENV, ""))


def _valid_key_id(value: object) -> str:
    key_id = str(value or "").strip().lower()
    return key_id if _KEY_ID.fullmatch(key_id) else ""


def _key_env_name(key_id: str) -> str:
    key_id = _valid_key_id(key_id)
    if not key_id:
        return ""
    return KEY_ENV_PREFIX + key_id.upper().replace("-", "_")


def _resolve_key_id(
    key_id: str,
    *,
    environ: dict | None = None,
) -> bytes:
    env = os.environ if environ is None else environ
    name = _key_env_name(key_id)
    return _normalise_key(env.get(name, "")) if name else b""


def _active_key_id(*, environ: dict | None = None) -> str:
    env = os.environ if environ is None else environ
    return _valid_key_id(env.get(ACTIVE_KEY_ID_ENV, ""))


def _verification_key_ids(*, environ: dict | None = None) -> list[str]:
    env = os.environ if environ is None else environ
    raw = str(env.get(VERIFY_KEY_IDS_ENV, "") or "")
    ids = []
    for part in raw.split(","):
        key_id = _valid_key_id(part)
        if key_id and key_id not in ids:
            ids.append(key_id)
    active = _active_key_id(environ=env)
    if active and active not in ids:
        ids.append(active)
    return ids[:16]


def authenticity_status(
    signing_key: str | bytes | None = None,
    *,
    environ: dict | None = None,
) -> dict:
    if signing_key is not None:
        configured = bool(_resolve_legacy_key(signing_key))
        return {
            "version": VERSION,
            "algorithm": ALGORITHM,
            "configured": configured,
            "mode": "explicit_legacy_key",
            "active_key_id": "",
            "active_key_configured": False,
            "retained_key_ids": [],
            "legacy_verification_configured": configured,
            "rotation_ready": False,
            "minimum_key_bytes": MIN_KEY_BYTES,
            "secret_exposed": False,
        }

    env = os.environ if environ is None else environ
    active = _active_key_id(environ=env)
    active_key = _resolve_key_id(active, environ=env) if active else b""
    retained = _verification_key_ids(environ=env)
    configured_retained = [
        key_id for key_id in retained
        if _resolve_key_id(key_id, environ=env)
    ]
    legacy = bool(_resolve_legacy_key(environ=env))
    return {
        "version": VERSION,
        "algorithm": ALGORITHM,
        "configured": bool(active_key or legacy),
        "mode": "keyring" if active else "legacy_single_key",
        "active_key_id": active,
        "active_key_configured": bool(active_key),
        "retained_key_ids": configured_retained,
        "legacy_verification_configured": legacy,
        "rotation_ready": bool(active and active_key and legacy),
        "minimum_key_bytes": MIN_KEY_BYTES,
        "secret_exposed": False,
    }


def _unsigned_receipt(
    provenance_receipt_sha: str,
    payload_sha: str,
    *,
    version: str,
    key_id: str = "",
    issue: str,
) -> dict:
    result = {
        "version": version,
        "algorithm": ALGORITHM,
        "status": "unavailable",
        "valid": False,
        "answer_provenance_receipt_sha256": provenance_receipt_sha,
        "signed_payload_sha256": payload_sha,
        "signature": "",
        "issues": [issue],
    }
    if version == VERSION:
        result["key_id"] = key_id
    return result


def sign_answer_provenance(
    answer_provenance: dict | None,
    *,
    signing_key: str | bytes | None = None,
    key_id: str | None = None,
    environ: dict | None = None,
) -> dict:
    provenance = dict(answer_provenance or {})
    provenance_receipt_sha = str(
        provenance.get("receipt_sha256") or ""
    ).strip()
    payload_sha = sha256(_canonical_bytes(provenance)).hexdigest()

    # Explicit keys retain Layer 104 semantics for tests/operator tooling.
    if signing_key is not None:
        key = _resolve_legacy_key(signing_key)
        version = LEGACY_VERSION
        selected_id = ""
    else:
        env = os.environ if environ is None else environ
        selected_id = _valid_key_id(key_id) or _active_key_id(environ=env)
        if selected_id:
            key = _resolve_key_id(selected_id, environ=env)
            version = VERSION
        else:
            key = _resolve_legacy_key(environ=env)
            version = LEGACY_VERSION

    if not re.fullmatch(r"[0-9a-f]{64}", provenance_receipt_sha):
        return _unsigned_receipt(
            provenance_receipt_sha,
            payload_sha,
            version=version,
            key_id=selected_id,
            issue="answer_provenance_receipt_invalid",
        )
    if not key:
        return _unsigned_receipt(
            provenance_receipt_sha,
            payload_sha,
            version=version,
            key_id=selected_id,
            issue="signing_key_unavailable",
        )

    signature = hmac.new(
        key,
        _canonical_bytes(provenance),
        sha256,
    ).hexdigest()
    result = {
        "version": version,
        "algorithm": ALGORITHM,
        "status": "signed",
        "valid": True,
        "answer_provenance_receipt_sha256": provenance_receipt_sha,
        "signed_payload_sha256": payload_sha,
        "signature": signature,
        "issues": [],
    }
    if version == VERSION:
        result["key_id"] = selected_id
    return result


def verify_answer_authenticity(
    authenticity: dict | None,
    answer_provenance: dict | None,
    *,
    signing_key: str | bytes | None = None,
    environ: dict | None = None,
) -> dict:
    if not isinstance(authenticity, dict):
        return {
            "version": VERSION,
            "valid": False,
            "authentic": False,
            "issues": ["answer_authenticity_missing_or_malformed"],
        }

    provenance = dict(answer_provenance or {})
    env = os.environ if environ is None else environ
    receipt_version = str(authenticity.get("version") or "")
    issues: list[str] = []
    key_id = ""

    if receipt_version == LEGACY_VERSION:
        key = _resolve_legacy_key(signing_key, environ=env)
        verification_mode = "legacy_layer104"
    elif receipt_version == VERSION:
        key_id = _valid_key_id(authenticity.get("key_id"))
        allowed = _verification_key_ids(environ=env)
        if not key_id:
            issues.append("answer_authenticity_key_id_invalid")
            key = b""
        elif key_id not in allowed:
            issues.append("answer_authenticity_key_id_not_retained")
            key = b""
        else:
            key = _resolve_key_id(key_id, environ=env)
        verification_mode = "keyring"
    else:
        issues.append("answer_authenticity_version_invalid")
        key = b""
        verification_mode = "unknown"

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
        "receipt_version": receipt_version,
        "valid": not issues,
        "authentic": not issues,
        "algorithm": ALGORITHM,
        "verification_mode": verification_mode,
        "key_id": key_id,
        "issues": issues,
        "answer_provenance_receipt_sha256": provenance_receipt_sha,
        "signed_payload_sha256": payload_sha if not issues else "",
    }
