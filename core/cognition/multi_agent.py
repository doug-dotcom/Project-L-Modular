"""Project L Phase 9: governed multi-agent cognition behind one L.

Workers are bounded functions, not personalities. Independent workers may run in
parallel; dependent reasoning waits for their visible outputs. Only L owns final
synthesis and user-facing voice authority.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Callable

from agents.quinn.quinn import curate_principles
from core.cognition.longitudinal import build_longitudinal_packet, needs_longitudinal_context


MULTI_AGENT_VERSION = "1.0"

WORKER_REGISTRY = {
    "rhee": {
        "role": "evidence_retrieval",
        "phase": "upstream_evidence",
        "dependencies": [],
    },
    "mary": {
        "role": "longitudinal_intelligence",
        "phase": "parallel_foundation",
        "dependencies": ["rhee"],
    },
    "quinn": {
        "role": "governed_principles",
        "phase": "parallel_foundation",
        "dependencies": [],
    },
    "rike": {
        "role": "hypothesis_and_counterfactual_reasoning",
        "phase": "dependent_reasoning",
        "dependencies": ["rhee", "mary", "quinn"],
    },
    "carol": {
        "role": "evidence_hygiene",
        "phase": "persistence_governance",
        "dependencies": ["rhee"],
    },
    "sara": {
        "role": "memory_governance",
        "phase": "persistence_governance",
        "dependencies": ["carol"],
    },
    "fiona": {
        "role": "financial_intelligence",
        "phase": "specialist_capability",
        "dependencies": [],
    },
    "deterministic_services": {
        "role": "authorised_external_capabilities",
        "phase": "specialist_capability",
        "dependencies": [],
    },
}


def _receipt(name: str, status: str, invoked: bool, error: str = "") -> dict:
    spec = WORKER_REGISTRY[name]
    return {
        "worker": name,
        "role": spec["role"],
        "phase": spec["phase"],
        "dependencies": list(spec["dependencies"]),
        "invoked": bool(invoked),
        "status": status,
        "error": str(error or "")[:500],
        "voice_authority": False,
        "decision_authority": False,
    }


def _mary_not_required() -> dict:
    return {
        "engine": "mary",
        "version": "5.0",
        "active": False,
        "status": "not_required",
        "lifecycle_state": "Candidate",
        "supporting_episodes": [],
        "contradicting_episodes": [],
        "confidence_trajectory": [],
        "current_relevance": "not_applicable",
        "current_identity_precedence": True,
        "pattern_threshold_met": False,
    }


def _quinn_not_required() -> dict:
    return {
        "engine": "quinn",
        "version": "2.0",
        "status": "not_required",
        "principles": [],
        "authority": "advisory",
    }


def run_parallel_foundation(
    message: str,
    evidence_context: str,
    structured_reasoning_required: bool,
    mary_builder: Callable[[str, str], dict] = build_longitudinal_packet,
    quinn_builder: Callable[[str], dict] = curate_principles,
    timeout_seconds: float = 2.0,
) -> dict:
    """Run independent Mary and Quinn work concurrently when the task earns it."""
    mary_required = needs_longitudinal_context(message)
    quinn_required = bool(structured_reasoning_required or mary_required)
    tasks = {}
    outputs = {
        "mary": _mary_not_required(),
        "quinn": _quinn_not_required(),
    }
    receipts = {
        "mary": _receipt("mary", "not_required", False),
        "quinn": _receipt("quinn", "not_required", False),
    }

    if not mary_required and not quinn_required:
        return {
            "engine": "parallel_cognitive_foundation",
            "version": MULTI_AGENT_VERSION,
            "parallel_execution": False,
            "invoked_workers": [],
            "outputs": outputs,
            "receipts": receipts,
        }

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="l-cognition") as executor:
        if mary_required:
            tasks["mary"] = executor.submit(mary_builder, message, evidence_context)
        if quinn_required:
            tasks["quinn"] = executor.submit(quinn_builder, message)
        for name in ("mary", "quinn"):
            future = tasks.get(name)
            if future is None:
                continue
            try:
                result = future.result(timeout=max(0.05, float(timeout_seconds)))
                if not isinstance(result, dict):
                    raise TypeError("worker_result_must_be_dict")
                outputs[name] = result
                receipts[name] = _receipt(name, "complete", True)
            except TimeoutError:
                future.cancel()
                receipts[name] = _receipt(name, "timeout", True, "bounded_worker_timeout")
            except Exception as exc:
                receipts[name] = _receipt(name, "error", True, f"{type(exc).__name__}: {exc}")

    invoked = [name for name in ("mary", "quinn") if receipts[name]["invoked"]]
    return {
        "engine": "parallel_cognitive_foundation",
        "version": MULTI_AGENT_VERSION,
        "parallel_execution": len(invoked) > 1,
        "invoked_workers": invoked,
        "outputs": outputs,
        "receipts": receipts,
    }


def build_multi_agent_packet(
    cognitive_plan: dict,
    rhee_packet: dict,
    capability_packet: dict,
    foundation_packet: dict,
    rike_packet: dict,
) -> dict:
    """Build the auditable worker topology without duplicating worker outputs."""
    plan = cognitive_plan or {}
    needs = plan.get("needs") or {}
    rhee = rhee_packet or {}
    capability = capability_packet or {}
    foundation = foundation_packet or {}
    rike = rike_packet or {}
    workers = dict(foundation.get("receipts") or {})

    if needs.get("memory"):
        rhee_status = "complete" if rhee.get("recall_active") else "no_evidence"
        workers["rhee"] = _receipt("rhee", rhee_status, True)
    else:
        workers["rhee"] = _receipt("rhee", "not_required", False)

    rike_invoked = rike.get("status") != "not_required"
    rike_status = (
        "complete" if rike.get("status") == "ok"
        else "not_required" if not rike_invoked
        else "degraded"
    )
    workers["rike"] = _receipt("rike", rike_status, rike_invoked)
    workers["carol"] = _receipt("carol", "not_required_in_response_path", False)
    workers["sara"] = _receipt("sara", "not_required_in_response_path", False)

    capability_name = str(capability.get("capability") or "l_core")
    capability_invoked = bool(capability.get("handled"))
    if capability_name == "financial_intelligence":
        workers["fiona"] = _receipt("fiona", str(capability.get("status") or "error"), True)
        workers["deterministic_services"] = _receipt(
            "deterministic_services", "not_required", False
        )
    else:
        workers["fiona"] = _receipt("fiona", "not_required", False)
        workers["deterministic_services"] = _receipt(
            "deterministic_services",
            str(capability.get("status") or "error") if capability_invoked else "not_required",
            capability_invoked,
        )

    ordered_workers = {
        name: workers.get(name, _receipt(name, "not_required", False))
        for name in WORKER_REGISTRY
    }
    governance_issues = []
    if any(item.get("voice_authority") for item in ordered_workers.values()):
        governance_issues.append("worker_voice_authority_violation")
    if any(item.get("decision_authority") for item in ordered_workers.values()):
        governance_issues.append("worker_decision_authority_violation")
    if set(ordered_workers) != set(WORKER_REGISTRY):
        governance_issues.append("worker_registry_incomplete")

    required_failures = [
        name for name, item in ordered_workers.items()
        if item["invoked"] and item["status"] in {"error", "timeout", "degraded"}
    ]
    return {
        "engine": "governed_multi_agent_cognition",
        "version": MULTI_AGENT_VERSION,
        "status": "degraded" if required_failures or governance_issues else "complete",
        "user_facing_voice": "L",
        "synthesis_owner": "L",
        "one_voice": True,
        "parallel_execution": bool(foundation.get("parallel_execution")),
        "execution_order": [
            "upstream_evidence",
            "parallel_foundation",
            "dependent_reasoning",
            "governed_synthesis",
        ],
        "workers": ordered_workers,
        "required_failures": required_failures,
        "governance": {
            "passed": not governance_issues,
            "issues": governance_issues,
            "worker_outputs_are_advisory": True,
            "worker_failures_are_isolated": True,
            "autonomous_external_actions": False,
            "internal_workers_must_not_speak_as_personas": True,
        },
    }


__all__ = [
    "MULTI_AGENT_VERSION",
    "WORKER_REGISTRY",
    "build_multi_agent_packet",
    "run_parallel_foundation",
]
