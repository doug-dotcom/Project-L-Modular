"""Project L Phase 8: post-task reflective metacognition.

Reflection inspects visible cognitive artefacts after a significant task. It does
not reveal hidden reasoning, invent missing evidence, or change durable learning.
"""

from __future__ import annotations

import re
from copy import deepcopy
from hashlib import sha256

from core.cognition.uncertainty import DIMENSIONS


REFLECTION_VERSION = "1.0"

CORRECTION_SIGNALS = (
    "you got that wrong",
    "that is wrong",
    "that's wrong",
    "that’s wrong",
    "not what i said",
    "i already told you",
    "i corrected you",
    "you misremembered",
)

INVALIDATION_SIGNALS = (
    "later evidence",
    "new evidence shows",
    "new evidence proved",
    "turned out to be wrong",
    "has been disproved",
    "was superseded",
    "later proved wrong",
)


def _check(status: str, passed: bool | None, basis: str, evidence=None) -> dict:
    return {
        "status": status,
        "passed": passed,
        "basis": str(basis),
        "evidence": list(evidence or []),
    }


def _retrieved_record_count(context: str) -> int:
    match = re.search(r"MEMORIES FOUND:\s*(\d+)", str(context or ""), re.I)
    if match:
        return int(match.group(1))
    return sum(
        bool(re.match(r"^\d+(?:\.\d+)?\s*\|\s*(?:memory_|local_)", line.strip(), re.I))
        for line in str(context or "").splitlines()
    )


def _explicit_signal(text: str, signals: tuple[str, ...]) -> str | None:
    lowered = " ".join(str(text or "").lower().split())
    return next((signal for signal in signals if signal in lowered), None)


def _confidence_is_calibrated(packet: dict) -> tuple[bool, list[str]]:
    confidence = (packet or {}).get("confidence_dimensions") or {}
    dimensions = confidence.get("dimensions") or {}
    issues = []
    if set(dimensions) != set(DIMENSIONS):
        issues.append("confidence_dimensions_incomplete")
    if confidence.get("aggregation") != "prohibited":
        issues.append("confidence_dimensions_aggregated")
    for name in DIMENSIONS:
        item = dimensions.get(name) or {}
        if item.get("applicable"):
            if item.get("level") not in {"low", "medium", "high"}:
                issues.append(f"{name}_level_invalid")
            score = item.get("score")
            if not isinstance(score, (int, float)) or not 0 <= score <= 1:
                issues.append(f"{name}_score_invalid")
            if not item.get("basis"):
                issues.append(f"{name}_basis_missing")
    return not issues, issues


def reflect_on_task(
    user_message: str,
    response: str,
    cognitive_packet: dict,
    rhee_packet: dict | None = None,
    capability_packet: dict | None = None,
    source_reference: str = "",
) -> dict:
    """Assess one completed significant task using only visible runtime packets."""
    cognitive = cognitive_packet or {}
    controller = cognitive.get("controller") or {}
    needs = controller.get("needs") or {}
    rhee = rhee_packet or {}
    capability = capability_packet or {}
    route = cognitive.get("route") or {}
    significant = bool(
        controller.get("substantial")
        or any(needs.values())
        or capability.get("handled")
    )
    if not significant:
        return {
            "engine": "reflective_metacognition",
            "version": REFLECTION_VERSION,
            "active": False,
            "status": "not_required",
            "source_reference": str(source_reference or "")[:500],
            "checks": {},
            "issues": [],
            "observations_for_learning": [],
            "auto_adjusted": False,
            "stored_growth": False,
        }

    checks = {}
    evidence_issues = []
    if needs.get("memory") and not rhee.get("recall_active"):
        evidence_issues.append("required_memory_not_retrieved")
    if needs.get("external_evidence") and not (
        capability.get("handled") and capability.get("status") == "ok"
    ):
        evidence_issues.append("required_external_evidence_unavailable")
    checks["enough_evidence_retrieved"] = _check(
        "attention" if evidence_issues else "passed",
        not evidence_issues,
        "Required retrieval and capability results were checked against the controller plan.",
        evidence_issues or ["all_required_evidence_channels_returned"],
    )

    retrieved = _retrieved_record_count(rhee.get("context", ""))
    budget = {"low": 8, "medium": 18, "high": 25}.get(controller.get("difficulty"), 18)
    over_retrieval = bool(
        (not needs.get("memory") and retrieved > 0)
        or (needs.get("memory") and retrieved > budget)
    )
    checks["over_retrieval"] = _check(
        "attention" if over_retrieval else "passed",
        not over_retrieval,
        "Retrieved records were compared with the task's deterministic evidence budget.",
        [f"records={retrieved}", f"budget={budget}"],
    )

    rike_required = bool(needs.get("structured_reasoning") or needs.get("longitudinal_reasoning"))
    rike_invoked = bool(
        route.get("rike") == "active"
        or (cognitive.get("rike") or {}).get("status") not in {None, "not_required"}
    )
    routing_correct = rike_required == rike_invoked
    checks["rike_invoked_appropriately"] = _check(
        "passed" if routing_correct else "attention",
        routing_correct,
        "RIKE activation was compared with the controller's structured-reasoning requirement.",
        [f"required={rike_required}", f"invoked={rike_invoked}"],
    )

    mary_contradictions = len((cognitive.get("mary") or {}).get("contradicting_episodes") or [])
    rike = cognitive.get("rike") or {}
    visible_contradictions = len(rike.get("conflicts") or []) + sum(
        len((item or {}).get("contradictory_evidence") or [])
        for item in rike.get("hypotheses") or []
        if isinstance(item, dict)
    )
    contradiction_missed = mary_contradictions > 0 and visible_contradictions == 0
    checks["contradictory_evidence_missed"] = _check(
        "attention" if contradiction_missed else "passed",
        not contradiction_missed,
        "Mary's contradictory episodes were checked against RIKE's visible conflict analysis.",
        [f"mary={mary_contradictions}", f"rike={visible_contradictions}"],
    )

    calibrated, calibration_issues = _confidence_is_calibrated(cognitive)
    checks["confidence_calibrated"] = _check(
        "passed" if calibrated else "attention",
        calibrated,
        "All six applicable confidence dimensions require a level, bounded score and basis; aggregation is prohibited.",
        calibration_issues or ["six_dimensions_valid"],
    )

    correction = _explicit_signal(user_message, CORRECTION_SIGNALS)
    checks["doug_corrected_system"] = _check(
        "observed" if correction else "not_observed",
        None,
        "Only an explicit correction phrase is recorded; absence is not treated as approval.",
        [correction] if correction else [],
    )

    invalidation = _explicit_signal(user_message, INVALIDATION_SIGNALS)
    checks["later_evidence_invalidated_conclusion"] = _check(
        "observed" if invalidation else "not_observed",
        None,
        "Only explicit later-evidence language is recorded; no invalidation is inferred.",
        [invalidation] if invalidation else [],
    )

    response_present = bool(str(response or "").strip())
    checks["completed_response_available"] = _check(
        "passed" if response_present else "attention",
        response_present,
        "Post-task reflection requires the completed response artefact.",
        [f"response_characters={len(str(response or ''))}"],
    )

    issues = [
        name for name, check in checks.items()
        if check.get("status") == "attention"
    ]
    learning_observations = list(issues)
    if correction:
        learning_observations.append("doug_correction_observed")
    if invalidation:
        learning_observations.append("later_evidence_invalidation_observed")

    return {
        "engine": "reflective_metacognition",
        "version": REFLECTION_VERSION,
        "active": True,
        "status": "attention_required" if learning_observations else "complete",
        "source_reference": str(source_reference or "")[:500],
        "response_fingerprint": sha256(str(response or "").encode("utf-8")).hexdigest(),
        "later_evidence": [],
        "checks": checks,
        "issues": issues,
        "observations_for_learning": learning_observations,
        "auto_adjusted": False,
        "stored_growth": False,
        "instruction": (
            "Send visible observations to Learning Engine 2 as traceable candidates. "
            "Do not change behaviour or store growth without the full outcome cycle."
        ),
    }


def record_later_evidence(
    reflection_packet: dict,
    evidence_reference: str,
    basis: str,
    invalidated_conclusion: bool,
) -> dict:
    """Attach a traceable later observation to an earlier task reflection."""
    reflection = deepcopy(reflection_packet or {})
    evidence_reference = str(evidence_reference or "").strip()[:500]
    basis = " ".join(str(basis or "").split()).strip()[:1200]
    if not reflection.get("active"):
        return {"status": "rejected", "reason": "active_reflection_required"}
    if not reflection.get("source_reference") or not evidence_reference or not basis:
        return {"status": "rejected", "reason": "linked_later_evidence_required"}

    evidence = {
        "evidence_reference": evidence_reference,
        "basis": basis,
        "invalidated_conclusion": bool(invalidated_conclusion),
    }
    reflection.setdefault("later_evidence", []).append(evidence)
    reflection.setdefault("checks", {})["later_evidence_invalidated_conclusion"] = _check(
        "observed" if invalidated_conclusion else "not_observed",
        None,
        "A linked later-evidence observation was explicitly assessed.",
        [evidence_reference, basis],
    )
    if invalidated_conclusion:
        observations = reflection.setdefault("observations_for_learning", [])
        if "later_evidence_invalidation_observed" not in observations:
            observations.append("later_evidence_invalidation_observed")
        reflection["status"] = "attention_required"
    reflection["auto_adjusted"] = False
    reflection["stored_growth"] = False
    return reflection


__all__ = ["REFLECTION_VERSION", "record_later_evidence", "reflect_on_task"]
