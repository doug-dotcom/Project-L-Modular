"""Constitutional checks for RIKE packets and L's response prompt."""

from __future__ import annotations


def assess_cognitive_packet(packet: dict, mary_packet: dict | None = None) -> dict:
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
    if not packet.get("uncertainties"):
        issues.append("uncertainty_review_missing")
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
        "- Preserve Doug's authority over consequential decisions.\n"
        "- Do not reveal hidden chain-of-thought; provide only a concise rationale.\n"
        f"- Pre-response review issues: {issues}."
    )
