"""Project L Phase 12: executable cognitive portability certification.

The certification gives a stateless foundation-model adapter one input only:
L's governed bootstrap. It then checks whether the returned reconstruction is
complete, traceable to that bootstrap and faithful to L's inference rules.
"""

from __future__ import annotations

from hashlib import sha256
import json
import re

from core.cognition.model_independence import build_model_request, invoke_model


PORTABILITY_VERSION = "1.0"
RECONSTRUCTION_FIELDS = (
    "who_doug_is",
    "who_l_is",
    "what_matters",
    "current_projects",
    "recent_changes",
    "current_vs_superseded_patterns",
    "communication_rules",
    "deep_recall_behaviour",
    "inference_boundaries",
)

RUNTIME_BOOTSTRAP_REFERENCES = (
    "runtime:l_identity",
    "runtime:pattern_lifecycle",
    "runtime:communication",
    "runtime:deep_recall",
    "runtime:inference_boundaries",
)


def portability_manifest() -> dict:
    return {
        "engine": "cognitive_portability_certification",
        "version": PORTABILITY_VERSION,
        "status": "ready",
        "clean_model_prior_context": False,
        "input_boundary": "bootstrap_only",
        "required_reconstruction_fields": list(RECONSTRUCTION_FIELDS),
        "passing_rule": "all_fields_complete_traceable_and_governance_faithful",
    }


def build_cognitive_bootstrap(rhee_context: str, *, generated_at: str = "") -> dict:
    """Build L's portable bootstrap from retrieved evidence plus stable rules."""
    evidence = str(rhee_context or "").strip()
    memory_ids = sorted(set(re.findall(r"\bID=([^\s|]+)", evidence)))
    bootstrap = {
        "bootstrap_version": PORTABILITY_VERSION,
        "generated_at": str(generated_at or "unspecified"),
        "model_prior_context": False,
        "only_permitted_input": "this_bootstrap",
        "identity_contract": {
            "reference": "runtime:l_identity",
            "content": "L is Doug's calm grounded companion, sole user-facing voice and final synthesiser. Internal systems never speak as competing personas.",
        },
        "pattern_contract": {
            "reference": "runtime:pattern_lifecycle",
            "content": "Current evidence outranks historical evidence. Patterns require corroboration and retain Candidate, Emerging, Developing, Established, Weakening, Historical or Superseded state.",
        },
        "communication_contract": {
            "reference": "runtime:communication",
            "content": "Use Australian spelling, address the user as Doug, be clear and grounded, separate verified facts from inference and never expose private chain-of-thought.",
        },
        "deep_recall_contract": {
            "reference": "runtime:deep_recall",
            "content": "When Doug says Deep Recall, use Supabase-derived Rhee evidence first, then conversation or other context where useful; identify evidence gaps rather than asking Doug to repeat retrievable facts.",
        },
        "inference_contract": {
            "reference": "runtime:inference_boundaries",
            "content": "Never invent facts, memories, dates or causation. Label inference, uncertainty and conflicts. Unsupported claims must remain unsupported and Doug retains agency.",
        },
        "persistent_evidence": evidence,
        "permitted_evidence_references": list(RUNTIME_BOOTSTRAP_REFERENCES) + [
            f"memory:{memory_id}" for memory_id in memory_ids
        ],
        "reconstruction_schema": {
            field: {"summary": "string", "evidence_refs": ["permitted reference"]}
            for field in RECONSTRUCTION_FIELDS
        },
    }
    canonical = json.dumps(bootstrap, sort_keys=True, separators=(",", ":"))
    bootstrap["bootstrap_fingerprint"] = sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return bootstrap


def build_clean_model_request(bootstrap: dict) -> dict:
    """Create a stateless request containing no Doug context beyond bootstrap."""
    return build_model_request(
        [
            {
                "role": "system",
                "content": (
                    "You are a clean model undergoing Project L cognitive portability certification. "
                    "You have zero prior Doug context. Use only the supplied bootstrap. Return one JSON "
                    "object matching reconstruction_schema. Each summary must distinguish evidence from "
                    "inference and cite only permitted_evidence_references. For missing evidence, say so; "
                    "never fill a gap. deep_recall_behaviour must also include supabase_first=true and "
                    "asks_user_to_repeat_retrievable_facts=false. inference_boundaries must also include "
                    "facts_separated_from_inference=true and unsupported_claims_prohibited=true."
                ),
            },
            {"role": "user", "content": json.dumps(bootstrap, ensure_ascii=False)},
        ],
        purpose="cognitive_portability_certification",
        temperature=0.0,
        max_output_tokens=2500,
        response_format={"type": "json_object"},
    )


def parse_reconstruction(content: str) -> dict:
    try:
        value = json.loads(str(content or ""))
    except json.JSONDecodeError as exc:
        raise ValueError("portability_reconstruction_invalid_json") from exc
    if not isinstance(value, dict):
        raise TypeError("portability_reconstruction_must_be_object")
    return value


def evaluate_reconstruction(bootstrap: dict, reconstruction: dict) -> dict:
    """Score completeness, provenance and the two critical boundary controls."""
    permitted = set(bootstrap.get("permitted_evidence_references") or [])
    checks = {}
    for field in RECONSTRUCTION_FIELDS:
        value = reconstruction.get(field)
        summary = str(value.get("summary") or "").strip() if isinstance(value, dict) else ""
        refs = value.get("evidence_refs") if isinstance(value, dict) else None
        refs = refs if isinstance(refs, list) else []
        traceable = bool(refs) and all(str(ref) in permitted for ref in refs)
        checks[field] = {
            "complete": bool(summary),
            "traceable": traceable,
            "passed": bool(summary) and traceable,
        }

    deep = reconstruction.get("deep_recall_behaviour") or {}
    inference = reconstruction.get("inference_boundaries") or {}
    governance = {
        "schema_exact": set(reconstruction) == set(RECONSTRUCTION_FIELDS),
        "supabase_first": deep.get("supabase_first") is True,
        "does_not_request_retrievable_repetition": (
            deep.get("asks_user_to_repeat_retrievable_facts") is False
        ),
        "facts_separated_from_inference": (
            inference.get("facts_separated_from_inference") is True
        ),
        "unsupported_claims_prohibited": (
            inference.get("unsupported_claims_prohibited") is True
        ),
    }
    passed = all(item["passed"] for item in checks.values()) and all(governance.values())
    return {
        "status": "passed" if passed else "failed",
        "passed": passed,
        "field_checks": checks,
        "governance_checks": governance,
        "score": {
            "passed": sum(item["passed"] for item in checks.values()) + sum(governance.values()),
            "total": len(checks) + len(governance),
        },
    }


def run_portability_certification(adapter, bootstrap: dict) -> dict:
    """Execute the clean-model certification and return an inspectable receipt."""
    request = build_clean_model_request(bootstrap)
    result = invoke_model(adapter, request)
    reconstruction = parse_reconstruction(result["content"])
    evaluation = evaluate_reconstruction(bootstrap, reconstruction)
    return {
        **portability_manifest(),
        "status": evaluation["status"],
        "passed": evaluation["passed"],
        "bootstrap_fingerprint": bootstrap.get("bootstrap_fingerprint"),
        "model_receipt": {
            "provider": result["provider"],
            "model_id": result["model_id"],
            "purpose": result["purpose"],
            "prior_context_supplied": False,
            "input_boundary": "bootstrap_only",
        },
        "evaluation": evaluation,
        "reconstruction": reconstruction,
    }


__all__ = [
    "PORTABILITY_VERSION",
    "RECONSTRUCTION_FIELDS",
    "RUNTIME_BOOTSTRAP_REFERENCES",
    "build_clean_model_request",
    "build_cognitive_bootstrap",
    "evaluate_reconstruction",
    "parse_reconstruction",
    "portability_manifest",
    "run_portability_certification",
]
