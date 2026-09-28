"""Independent Shine-AI decision trace verification for Project L.

This module mirrors Shine-AI's documented Layer 137 control-plane digest
contract without importing Shine-AI code. It verifies only non-content
receipts: planning, recovery, execution, grounding counts, verification counts,
delivery mode and release identity.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
KEY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SIGNATURE_B64_RE = re.compile(r"^[A-Za-z0-9+/]{86}==$")
VERIFICATION_VERSION = "shine-ai/decision-trace-verification-v1"
AUTHENTICITY_VERSION = "shine-ai/decision-trace-authenticity-v1"
SIGNATURE_DOMAIN = "shine-ai:decision-trace:v1"


def _digest(material: dict[str, Any]) -> str:
    canonical = json.dumps(
        material,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("invalid-object")
    return value


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("invalid-string-list")
    return list(value)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("invalid-optional-string")
    return value


def _normalise_memory(value: Any) -> dict[str, list[str]]:
    data = _dict(value)
    return {
        str(source): sorted(set(_string_list(scopes)))
        for source, scopes in sorted(data.items())
    }


def _planning_material(value: Any) -> dict[str, Any]:
    item = _dict(value)
    if item.get("version") != 1:
        raise ValueError("planning-version")
    return {
        "version": 1,
        "tool_source": item.get("tool_source"),
        "selected_tools": _string_list(item.get("selected_tools")),
        "memory_source": item.get("memory_source"),
        "selected_memory": _normalise_memory(item.get("selected_memory")),
        "route": item.get("route"),
        "provider": _optional_string(item.get("provider")),
        "model": _optional_string(item.get("model")),
        "model_tier": _optional_string(item.get("model_tier")),
        "routing_score": item.get("routing_score"),
        "max_output_tokens": item.get("max_output_tokens"),
        "context_budget_chars": item.get("context_budget_chars"),
        "context_budget_items": item.get("context_budget_items"),
        "deferred_controls": _string_list(item.get("deferred_controls")),
    }


def _recovery_material(value: Any) -> dict[str, Any]:
    item = _dict(value)
    if item.get("version") != 1:
        raise ValueError("recovery-version")
    return {
        "version": 1,
        "mode": item.get("mode"),
        "failure_stage": item.get("failure_stage"),
        "action": item.get("action"),
        "automatic_retry_count": item.get("automatic_retry_count"),
    }


def _execution_material(value: Any) -> dict[str, Any]:
    item = _dict(value)
    if item.get("version") != 1:
        raise ValueError("execution-version")
    return {
        "version": 1,
        "status": item.get("status"),
        "route": item.get("route"),
        "provider": _optional_string(item.get("provider")),
        "model": _optional_string(item.get("model")),
        "model_tier": _optional_string(item.get("model_tier")),
        "max_output_tokens": item.get("max_output_tokens"),
        "tools": _string_list(item.get("tools")),
        "memory": _normalise_memory(item.get("memory")),
        "context_budget_chars": item.get("context_budget_chars"),
        "context_budget_items": item.get("context_budget_items"),
        "adjustments": _string_list(item.get("adjustments")),
    }


def _grounding_material(value: Any) -> dict[str, Any]:
    item = _dict(value)
    return {
        "evidence_available": item.get("evidence_available"),
        "selected_evidence_count": len(_string_list(item.get("selected_evidence_ids"))),
        "cited_evidence_count": len(_string_list(item.get("cited_evidence_ids"))),
        "unknown_citation_count": len(_string_list(item.get("unknown_citation_ids"))),
        "citation_coverage": item.get("citation_coverage"),
    }


def _verification_material(value: Any) -> dict[str, Any]:
    item = _dict(value)
    return {
        "mode": item.get("mode"),
        "evidence_required": item.get("evidence_required"),
        "evidence_available": item.get("evidence_available"),
        "cited_evidence_count": item.get("cited_evidence_count"),
        "unknown_citation_count": item.get("unknown_citation_count"),
        "required_memory_sources": sorted(set(_string_list(item.get("required_memory_sources")))),
        "cited_memory_sources": sorted(set(_string_list(item.get("cited_memory_sources")))),
        "required_tool_request_count": len(
            _string_list(item.get("required_tool_request_ids"))
        ),
        "cited_tool_request_count": len(
            _string_list(item.get("cited_tool_request_ids"))
        ),
        "warning_count": len(_string_list(item.get("warnings"))),
    }


def _delivery_material(value: Any) -> dict[str, Any]:
    item = _dict(value)
    return {"mode": item.get("mode")}


def recompute_decision_trace(response_data: Any) -> dict[str, Any] | None:
    if not isinstance(response_data, dict):
        return None
    trace = response_data.get("decision_trace")
    if not isinstance(trace, dict):
        return None

    try:
        service_version = str(trace.get("service_version") or "").strip()
        service_release = str(trace.get("service_release") or "").strip()
        if not service_version or not service_release:
            return None

        contract = response_data.get("response_profile_contract_sha256")
        if contract is not None and (
            not isinstance(contract, str) or SHA256_RE.fullmatch(contract) is None
        ):
            return None

        planning_sha256 = _digest(_planning_material(response_data.get("planning")))
        recovery_sha256 = _digest(_recovery_material(response_data.get("recovery")))
        execution_sha256 = _digest(_execution_material(response_data.get("execution")))
        grounding_sha256 = _digest(_grounding_material(response_data.get("grounding")))
        verification_sha256 = _digest(
            _verification_material(response_data.get("verification"))
        )
        delivery_sha256 = _digest(_delivery_material(response_data.get("delivery")))

        lineage = {
            "version": 1,
            "algorithm": "sha256",
            "scope": "control-plane",
            "service_version": service_version,
            "service_release": service_release,
            "response_profile_contract_sha256": contract,
            "planning_sha256": planning_sha256,
            "recovery_sha256": recovery_sha256,
            "execution_sha256": execution_sha256,
            "grounding_sha256": grounding_sha256,
            "verification_sha256": verification_sha256,
            "delivery_sha256": delivery_sha256,
        }
        return {
            **lineage,
            "lineage_sha256": _digest(lineage),
        }
    except (TypeError, ValueError):
        return None


def verify_decision_trace(
    response_data: Any,
    *,
    header_version: str | None = None,
    header_release: str | None = None,
    require_response_identity: bool = False,
) -> dict[str, Any]:
    trace = response_data.get("decision_trace") if isinstance(response_data, dict) else None
    if not isinstance(trace, dict):
        return {
            "version": VERIFICATION_VERSION,
            "status": "unavailable",
            "verified": False,
            "reason_code": "decision-trace-missing",
        }

    required_fields = (
        "planning_sha256",
        "recovery_sha256",
        "execution_sha256",
        "grounding_sha256",
        "verification_sha256",
        "delivery_sha256",
        "lineage_sha256",
    )
    if (
        trace.get("version") != 1
        or trace.get("algorithm") != "sha256"
        or trace.get("scope") != "control-plane"
        or any(
            not isinstance(trace.get(field), str)
            or SHA256_RE.fullmatch(trace[field]) is None
            for field in required_fields
        )
    ):
        return {
            "version": VERIFICATION_VERSION,
            "status": "invalid",
            "verified": False,
            "reason_code": "decision-trace-format-invalid",
        }

    service_version = str(trace.get("service_version") or "")
    service_release = str(trace.get("service_release") or "")
    if require_response_identity and (not header_version or not header_release):
        return {
            "version": VERIFICATION_VERSION,
            "status": "invalid",
            "verified": False,
            "reason_code": "decision-trace-response-identity-missing",
            "service_version": service_version,
            "service_release": service_release,
        }
    if header_version and service_version != header_version:
        return {
            "version": VERIFICATION_VERSION,
            "status": "invalid",
            "verified": False,
            "reason_code": "decision-trace-version-header-mismatch",
            "service_version": service_version,
            "service_release": service_release,
        }
    if header_release and service_release != header_release:
        return {
            "version": VERIFICATION_VERSION,
            "status": "invalid",
            "verified": False,
            "reason_code": "decision-trace-release-header-mismatch",
            "service_version": service_version,
            "service_release": service_release,
        }

    recomputed = recompute_decision_trace(response_data)
    if recomputed is None:
        return {
            "version": VERIFICATION_VERSION,
            "status": "invalid",
            "verified": False,
            "reason_code": "decision-trace-recompute-failed",
            "service_version": service_version,
            "service_release": service_release,
        }

    compare_fields = (
        "version",
        "algorithm",
        "scope",
        "service_version",
        "service_release",
        "response_profile_contract_sha256",
        *required_fields,
    )
    mismatches = [
        field
        for field in compare_fields
        if recomputed.get(field) != trace.get(field)
    ]
    if mismatches:
        return {
            "version": VERIFICATION_VERSION,
            "status": "invalid",
            "verified": False,
            "reason_code": "decision-trace-digest-mismatch",
            "mismatch_count": len(mismatches),
            "service_version": service_version,
            "service_release": service_release,
            "lineage_sha256": str(trace.get("lineage_sha256") or ""),
            "recomputed_lineage_sha256": recomputed["lineage_sha256"],
        }

    return {
        "version": VERIFICATION_VERSION,
        "status": "verified",
        "verified": True,
        "service_version": service_version,
        "service_release": service_release,
        "lineage_sha256": recomputed["lineage_sha256"],
    }


def digest_verification_keyset(keyset: Any) -> str | None:
    if not isinstance(keyset, dict):
        return None
    active_key_id = keyset.get("active_key_id")
    verification_keys = keyset.get("verification_keys")
    declared = keyset.get("keyset_sha256")
    if (
        not isinstance(active_key_id, str)
        or KEY_ID_RE.fullmatch(active_key_id) is None
        or not isinstance(verification_keys, dict)
        or not isinstance(declared, str)
        or SHA256_RE.fullmatch(declared) is None
        or not 1 <= len(verification_keys) <= 4
    ):
        return None

    clean_keys: dict[str, dict[str, str]] = {}
    for key_id in sorted(verification_keys):
        value = verification_keys.get(key_id)
        if (
            not isinstance(key_id, str)
            or KEY_ID_RE.fullmatch(key_id) is None
            or not isinstance(value, dict)
            or not isinstance(value.get("public_key_b64"), str)
            or not isinstance(value.get("public_key_sha256"), str)
            or SHA256_RE.fullmatch(value["public_key_sha256"]) is None
        ):
            return None
        try:
            public_bytes = base64.b64decode(
                value["public_key_b64"].strip(),
                validate=True,
            )
        except Exception:
            return None
        if (
            len(public_bytes) != 32
            or hashlib.sha256(public_bytes).hexdigest()
            != value["public_key_sha256"]
        ):
            return None
        clean_keys[key_id] = {
            "public_key_b64": value["public_key_b64"],
            "public_key_sha256": value["public_key_sha256"],
        }

    if active_key_id not in clean_keys:
        return None

    computed = _digest({"version": 1, "keys": clean_keys})
    return computed if computed == declared else None


def verify_decision_trace_authenticity(
    response_data: Any,
    *,
    trusted_keyset: Any,
    accepted_keyset_sha256: list[str] | tuple[str, ...],
    header_version: str | None,
    header_release: str | None,
) -> dict[str, Any]:
    verification = verify_decision_trace(
        response_data,
        header_version=header_version,
        header_release=header_release,
        require_response_identity=True,
    )
    if verification.get("status") != "verified":
        return {
            "version": AUTHENTICITY_VERSION,
            "status": "invalid",
            "authenticated": False,
            "reason_code": "decision-trace-verification-failed",
        }

    if (
        not isinstance(accepted_keyset_sha256, (list, tuple))
        or not 1 <= len(accepted_keyset_sha256) <= 4
        or any(
            not isinstance(value, str)
            or SHA256_RE.fullmatch(value) is None
            for value in accepted_keyset_sha256
        )
    ):
        return {
            "version": AUTHENTICITY_VERSION,
            "status": "unavailable",
            "authenticated": False,
            "reason_code": "trusted-keyset-pin-unavailable",
        }

    keyset_sha256 = digest_verification_keyset(trusted_keyset)
    if (
        keyset_sha256 is None
        or keyset_sha256 not in set(accepted_keyset_sha256)
    ):
        return {
            "version": AUTHENTICITY_VERSION,
            "status": "invalid",
            "authenticated": False,
            "reason_code": "trusted-keyset-mismatch",
        }

    signature = (
        response_data.get("decision_trace_signature")
        if isinstance(response_data, dict)
        else None
    )
    trace = (
        response_data.get("decision_trace")
        if isinstance(response_data, dict)
        else None
    )
    if (
        not isinstance(signature, dict)
        or signature.get("version") != 1
        or signature.get("algorithm") != "ed25519"
        or signature.get("domain") != SIGNATURE_DOMAIN
        or not isinstance(signature.get("key_id"), str)
        or KEY_ID_RE.fullmatch(signature["key_id"]) is None
        or not isinstance(signature.get("public_key_sha256"), str)
        or SHA256_RE.fullmatch(signature["public_key_sha256"]) is None
        or not isinstance(signature.get("signature_b64"), str)
        or SIGNATURE_B64_RE.fullmatch(signature["signature_b64"]) is None
        or not isinstance(trace, dict)
        or not isinstance(trace.get("lineage_sha256"), str)
        or SHA256_RE.fullmatch(trace["lineage_sha256"]) is None
    ):
        return {
            "version": AUTHENTICITY_VERSION,
            "status": "invalid",
            "authenticated": False,
            "reason_code": "decision-trace-signature-invalid",
            "keyset_sha256": keyset_sha256,
        }

    verification_keys = trusted_keyset.get("verification_keys", {})
    key = verification_keys.get(signature["key_id"])
    if not isinstance(key, dict):
        return {
            "version": AUTHENTICITY_VERSION,
            "status": "invalid",
            "authenticated": False,
            "reason_code": "decision-trace-signing-key-unknown",
            "keyset_sha256": keyset_sha256,
        }
    if key.get("public_key_sha256") != signature["public_key_sha256"]:
        return {
            "version": AUTHENTICITY_VERSION,
            "status": "invalid",
            "authenticated": False,
            "reason_code": "decision-trace-public-key-mismatch",
            "keyset_sha256": keyset_sha256,
        }

    try:
        public_bytes = base64.b64decode(
            str(key.get("public_key_b64") or "").strip(),
            validate=True,
        )
        signature_bytes = base64.b64decode(
            signature["signature_b64"],
            validate=True,
        )
        if len(public_bytes) != 32 or len(signature_bytes) != 64:
            raise ValueError("invalid-ed25519-length")
        if hashlib.sha256(public_bytes).hexdigest() != signature["public_key_sha256"]:
            raise ValueError("public-key-fingerprint-mismatch")
        Ed25519PublicKey.from_public_bytes(public_bytes).verify(
            signature_bytes,
            (
                SIGNATURE_DOMAIN
                + "\n"
                + signature["key_id"]
                + "\n"
                + trace["lineage_sha256"]
            ).encode("utf-8"),
        )
    except Exception:
        return {
            "version": AUTHENTICITY_VERSION,
            "status": "invalid",
            "authenticated": False,
            "reason_code": "decision-trace-signature-verification-failed",
            "key_id": signature["key_id"],
            "keyset_sha256": keyset_sha256,
        }

    return {
        "version": AUTHENTICITY_VERSION,
        "status": "authenticated",
        "authenticated": True,
        "key_id": signature["key_id"],
        "public_key_sha256": signature["public_key_sha256"],
        "keyset_sha256": keyset_sha256,
        "service_version": verification.get("service_version"),
        "service_release": verification.get("service_release"),
        "lineage_sha256": verification.get("lineage_sha256"),
    }


__all__ = [
    "AUTHENTICITY_VERSION",
    "VERIFICATION_VERSION",
    "digest_verification_keyset",
    "recompute_decision_trace",
    "verify_decision_trace",
    "verify_decision_trace_authenticity",
]
