"""Phase 5: governed abstraction of higher-order principles from experience."""

from __future__ import annotations

from agents.quinn.quinn import evaluate_candidate_principle


VALID_LONGITUDINAL_STATES = {"Developing", "Established"}


def _source_reference(episode: dict) -> str:
    table = str((episode or {}).get("table") or "").strip()
    source_id = str((episode or {}).get("id") or "").strip()
    if table and source_id:
        return f"{table}:{source_id}"
    return str((episode or {}).get("evidence_ref") or "").strip()[:500]


def _unique(values: list[str], limit: int = 12) -> list[str]:
    result = []
    seen = set()
    for value in values:
        clean = str(value or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result[:limit]


def build_experience_abstraction(
    question: str,
    mary_packet: dict,
    rike_packet: dict,
    quinn_packet: dict,
    guardrails: dict,
) -> dict:
    """Build an inspectable candidate; never promote it inside the reasoning turn."""
    mary_packet = mary_packet or {}
    rike_packet = rike_packet or {}
    supporting = list(mary_packet.get("supporting_episodes") or [])
    contradicting = list(mary_packet.get("contradicting_episodes") or [])
    source_refs = _unique([_source_reference(item) for item in supporting])
    contradiction_refs = _unique([_source_reference(item) for item in contradicting])
    candidate = str(rike_packet.get("conclusion") or "").strip()[:1200]

    rhee_passed = len(source_refs) >= 2
    mary_passed = bool(
        mary_packet.get("pattern_threshold_met")
        and mary_packet.get("lifecycle_state") in VALID_LONGITUDINAL_STATES
        and mary_packet.get("current_relevance") in {"current", "mixed"}
        and mary_packet.get("first_seen")
        and mary_packet.get("last_seen")
    )
    rike_passed = bool(
        rike_packet.get("status") == "ok"
        and len(rike_packet.get("hypotheses") or []) >= 2
        and rike_packet.get("alternative_explanations")
        and rike_packet.get("conclusion_change_evidence")
    )
    quinn_evaluation = evaluate_candidate_principle(
        candidate,
        question=question,
        curated_packet=quinn_packet,
    )

    rejection_reasons = []
    if not candidate:
        rejection_reasons.append("no_candidate_principle")
    if not rhee_passed:
        rejection_reasons.append("insufficient_independent_experiences")
    if not rike_passed:
        rejection_reasons.append("rike_challenge_incomplete")
    if not mary_passed:
        rejection_reasons.append("longitudinal_validation_incomplete")
    if not quinn_evaluation["passed"]:
        rejection_reasons.extend(quinn_evaluation["issues"])
    if not (guardrails or {}).get("passed"):
        rejection_reasons.append("cognitive_guardrails_failed")

    active = bool(mary_packet.get("active") and len(supporting) >= 2)
    promotion_eligible = bool(active and not rejection_reasons)
    return {
        "engine": "experience_abstraction",
        "version": "1.0",
        "active": active,
        "status": (
            "eligible_for_governed_promotion"
            if promotion_eligible else
            "candidate_requires_more_validation"
            if active else
            "no_candidate"
        ),
        "candidate_principle": candidate if active else "",
        "candidate_kind": "higher_order_principle" if active else None,
        "source_references": source_refs,
        "contradiction_references": contradiction_refs,
        "evaluations": {
            "rhee": {
                "passed": rhee_passed,
                "independent_experience_count": len(source_refs),
            },
            "quinn": quinn_evaluation,
            "rike": {
                "passed": rike_passed,
                "hypothesis_count": len(rike_packet.get("hypotheses") or []),
                "alternative_explanations_tested": bool(rike_packet.get("alternative_explanations")),
                "conclusion_change_tested": bool(rike_packet.get("conclusion_change_evidence")),
            },
            "mary": {
                "passed": mary_passed,
                "lifecycle_state": mary_packet.get("lifecycle_state"),
                "first_seen": mary_packet.get("first_seen"),
                "last_seen": mary_packet.get("last_seen"),
                "current_relevance": mary_packet.get("current_relevance"),
            },
        },
        "governance": {
            "promotion_eligible": promotion_eligible,
            "auto_promoted": False,
            "requires_doug_approval": True,
            "rejection_reasons": list(dict.fromkeys(rejection_reasons)),
        },
        "instruction": (
            "Present this only as a candidate higher-order principle until Doug explicitly "
            "approves governed promotion. No candidate is also a valid outcome."
        ),
    }


__all__ = ["build_experience_abstraction"]
