"""Independent Shine-AI decision trace verification for Project L.

This module mirrors Shine-AI's documented Layer 137 control-plane digest
contract without importing Shine-AI code. It verifies only non-content
receipts: planning, recovery, execution, grounding counts, verification counts,
delivery mode and release identity.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
VERIFICATION_VERSION = "shine-ai/decision-trace-verification-v1"


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


__all__ = [
    "VERIFICATION_VERSION",
    "recompute_decision_trace",
    "verify_decision_trace",
]
