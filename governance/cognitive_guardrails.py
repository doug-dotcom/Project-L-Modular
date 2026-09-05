"""Constitutional checks for RIKE packets and L's response prompt."""

from __future__ import annotations

from core.cognition.rike import CAUSAL_RELATIONSHIPS


MARY_LIFECYCLE_STATES = {
    "Candidate", "Emerging", "Developing", "Established",
    "Weakening", "Historical", "Superseded",
}


def assess_cognitive_packet(
    packet: dict,
    mary_packet: dict | None = None,
    confidence_dimensions: dict | None = None,
) -> dict:
    packet = packet or {}
    mary_packet = mary_packet or {}
    issues = []
    confidence = packet.get("confidence") or {}
    if confidence.get("level") not in {"low", "medium", "high"}:
        issues.append("confidence_not_calibrated")
    if packet.get("status") == "ok" and not packet.get("evidence_summary"):
        issues.append("evidence_summary_missing")
    if mary_packet.get("active") and not mary_packet.get("pattern_threshold_met"):
        issues.append("pattern_claim_requires_caution")
    if mary_packet.get("active"):
        if mary_packet.get("lifecycle_state") not in MARY_LIFECYCLE_STATES:
            issues.append("pattern_lifecycle_invalid")
        required_mary_fields = {
            "first_seen", "last_seen", "supporting_episodes",
            "contradicting_episodes", "confidence_trajectory", "current_relevance",
        }
        if not required_mary_fields.issubset(mary_packet):
            issues.append("longitudinal_evidence_incomplete")
        if mary_packet.get("current_identity_precedence") is not True:
            issues.append("current_identity_precedence_missing")
    if not packet.get("uncertainties"):
        issues.append("uncertainty_review_missing")
    if packet.get("status") == "ok":
        hypotheses = packet.get("hypotheses") or []
        if len(hypotheses) < 2:
            issues.append("competing_hypotheses_missing")
        required_hypothesis_fields = {
            "claim", "supporting_evidence", "contradictory_evidence",
            "assumptions", "alternative_explanations", "status",
        }
        if any(not isinstance(item, dict) or not required_hypothesis_fields.issubset(item) for item in hypotheses):
            issues.append("hypothesis_evidence_test_incomplete")
        alternatives = packet.get("alternative_explanations") or []
        hypothesis_alternatives = any(
            isinstance(item, dict) and item.get("alternative_explanations")
            for item in hypotheses
        )
        if not alternatives and not hypothesis_alternatives:
            issues.append("alternative_explanations_missing")
        if not packet.get("conclusion_change_evidence"):
            issues.append("conclusion_change_test_missing")
        counterfactuals = packet.get("counterfactuals") or []
        if not counterfactuals or any(
            not isinstance(item, dict)
            or not all(item.get(field) for field in ("condition", "expected_result", "implication"))
            for item in counterfactuals
        ):
            issues.append("counterfactual_test_missing")
        causal = packet.get("causal_assessment") or {}
        relationship = causal.get("relationship")
        if relationship not in CAUSAL_RELATIONSHIPS:
            issues.append("causal_relationship_unclassified")
        direct_established = bool((packet.get("direct_causal_evidence") or {}).get("established"))
        direct_verified = bool((packet.get("direct_causal_evidence") or {}).get("verified_against_context"))
        causal_supported = causal.get("supported_causal_claim") is True
        if causal_supported != direct_established:
            issues.append("causal_evidence_inconsistent")
        if (causal_supported or direct_established) and relationship != "supported_causal_claim":
            issues.append("causal_claim_exceeds_classification")
        if relationship == "supported_causal_claim" and not (causal_supported and direct_established):
            issues.append("causal_claim_lacks_direct_evidence")
        if direct_established and not direct_verified:
            issues.append("causal_evidence_not_verified_against_context")
    if confidence_dimensions is not None:
        dimensions = (confidence_dimensions or {}).get("dimensions") or {}
        required = {"source", "retrieval", "memory", "interpretation", "reasoning", "prediction"}
        if set(dimensions) != required:
            issues.append("confidence_dimensions_incomplete")
        if (confidence_dimensions or {}).get("aggregation") != "prohibited":
            issues.append("confidence_dimensions_improperly_aggregated")
    return {
        "engine": "project_l_cognitive_guardrails",
        "version": "1.0",
        "passed": not issues,
        "issues": issues,
        "agency_rule": "Present supported options and recommendations; consequential authority remains with Doug.",
        "drift_rule": "Answer Doug's actual request and do not invent goals, memories or evidence.",
    }


def guardrail_prompt(assessment: dict) -> str:
    issues = ", ".join((assessment or {}).get("issues") or []) or "none"
    return (
        "COGNITIVE GUARDRAILS:\n"
        "- Separate retrieved evidence from inference.\n"
        "- Do not turn one observation into a pattern.\n"
        "- State material uncertainty and contradictions.\n"
        "- Keep source, retrieval, memory, interpretation, reasoning and prediction confidence separate.\n"
        "- Never collapse the confidence dimensions into one overall score.\n"
        "- Compare competing hypotheses and preserve evidence both for and against each.\n"
        "- Expose material assumptions, alternatives, counterfactuals and what evidence would change the conclusion.\n"
        "- Keep correlation, association, plausible mechanism and supported causal claims distinct.\n"
        "- Never state a supported cause unless direct causal evidence passed RIKE's causal gate.\n"
        "- Use Mary's lifecycle state; never flatten Candidate, Emerging, Developing, Established, Weakening, Historical and Superseded.\n"
        "- Current identity and current evidence outrank historical patterns. Doug today must not be collapsed into historical Doug.\n"
        "- Experience abstraction is candidate wisdom, not fact. It requires Rhee evidence, Quinn review, RIKE challenge, Mary validation and governed promotion.\n"
        "- Never store a higher-order principle without explicit Doug approval; no durable principle is a valid outcome.\n"
        "- Preserve Doug's authority over consequential decisions.\n"
        "- Do not reveal hidden chain-of-thought; provide only a concise rationale.\n"
        f"- Pre-response review issues: {issues}."
    )
