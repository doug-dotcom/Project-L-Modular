"""Canonical, provenance-gated Project L learning engine.

Legacy Allegra storage remains as a compatibility datastore, but no autonomous
agent infers lessons from L's own replies. Only explicit Doug-authored learning
observations become candidates, and retrieval applies the existing independent-
source and contradiction thresholds.
"""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone

from agents.allegra.growth_retrieval import retrieve_growth_context, retrieve_growth_records
from agents.allegra.llgr_storage import store_llgr
from memory.promotion.gate import evaluate_promotion


LEARNING_PATTERNS = (
    re.compile(r"\bi (?:have )?learned that\s+(.+)", re.I),
    re.compile(r"\bi (?:have )?realised that\s+(.+)", re.I),
    re.compile(r"\bi (?:have )?realized that\s+(.+)", re.I),
    re.compile(r"\bwhat works for me is\s+(.+)", re.I),
    re.compile(r"\bwhat does not work for me is\s+(.+)", re.I),
    re.compile(r"\bwhat doesn't work for me is\s+(.+)", re.I),
)

LEARNING_STAGES = (
    "experience", "reflection", "candidate_lesson", "evidence_retrieval",
    "contradiction_search", "validation", "adjustment", "future_observation",
    "outcome", "confidence_update", "stored_growth",
)

OUTCOME_EFFECTS = {
    "supported": 0.15,
    "partly_supported": 0.05,
    "contradicted": -0.25,
    "inconclusive": 0.0,
}


def extract_user_learning(row: dict) -> dict | None:
    promotion = evaluate_promotion(row)
    if not promotion.get("promote") or str((row or {}).get("role") or "").lower() != "user":
        return None
    content = str((row or {}).get("content") or "").strip()
    for pattern in LEARNING_PATTERNS:
        match = pattern.search(content)
        if not match:
            continue
        lesson = match.group(1).strip().rstrip(".")
        if len(lesson.split()) < 3:
            return None
        return {
            "lesson": lesson,
            "validated": True,
            "evidence": [content[:1200]],
            "reflection": ["Doug-authored explicit learning observation"],
            "contradiction_count": 0,
        }
    return None


def record_user_learning(row: dict, client=None) -> dict:
    candidate = extract_user_learning(row)
    if not candidate:
        return {"stored": False, "reason": "not_explicit_user_learning"}
    raw_id = (row or {}).get("id")
    if raw_id is None:
        return {"stored": False, "reason": "missing_source_provenance"}
    try:
        return store_llgr(
            candidate,
            source_reference=f"raw_catchall:{raw_id}",
            client=client,
        )
    except Exception as exc:
        return {"stored": False, "reason": f"learning_store_error:{type(exc).__name__}"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stage(status: str, evidence=None) -> dict:
    return {"status": status, "evidence": evidence if evidence is not None else []}


def _validation_chain_passed(abstraction_packet: dict) -> bool:
    evaluations = (abstraction_packet or {}).get("evaluations") or {}
    return all(
        (evaluations.get(stage) or {}).get("passed") is True
        for stage in ("rhee", "quinn", "rike", "mary")
    )


def _initial_learning_confidence(source_count: int, contradiction_count: int) -> float:
    score = 0.3 + min(0.4, max(0, source_count) * 0.1)
    score -= min(0.3, max(0, contradiction_count) * 0.1)
    return round(max(0.05, min(0.8, score)), 2)


def build_learning_cycle(
    abstraction_packet: dict,
    reflection: str = "",
    adjustment: str = "",
) -> dict:
    """Create the pre-outcome portion of Learning Engine 2's state machine."""
    abstraction = abstraction_packet or {}
    lesson = str(abstraction.get("candidate_principle") or "").strip()
    sources = list(dict.fromkeys(abstraction.get("source_references") or []))
    contradictions = list(dict.fromkeys(abstraction.get("contradiction_references") or []))
    reflection = " ".join(str(reflection or "").split()).strip()[:1600]
    adjustment = " ".join(str(adjustment or "").split()).strip()[:1200]
    validation_passed = bool(
        (abstraction.get("governance") or {}).get("promotion_eligible")
        and _validation_chain_passed(abstraction)
    )
    contradiction_search_complete = "contradiction_references" in abstraction
    adjustment_complete = bool(adjustment) or not contradictions
    initial_confidence = _initial_learning_confidence(len(sources), len(contradictions))

    mary_state = (
        ((abstraction.get("evaluations") or {}).get("mary") or {})
        .get("lifecycle_state")
    )
    terminal_rejections = {
        "candidate_principle_overgeneralised", "cognitive_guardrails_failed",
    }
    rejection_reasons = set(
        ((abstraction.get("governance") or {}).get("rejection_reasons") or [])
    )
    if not abstraction.get("active"):
        status = "not_required"
        decision = "no_candidate"
    elif rejection_reasons & terminal_rejections or mary_state in {
        "Weakening", "Historical", "Superseded",
    }:
        status = "no_durable_lesson"
        decision = "no_durable_lesson"
    elif not validation_passed:
        status = "insufficient_evidence"
        decision = "defer"
    elif not adjustment_complete:
        status = "awaiting_adjustment"
        decision = "defer"
    else:
        status = "awaiting_future_observation"
        decision = "test_in_future"

    stages = {
        "experience": _stage("complete" if sources else "incomplete", sources),
        "reflection": _stage("complete" if reflection else "incomplete", [reflection] if reflection else []),
        "candidate_lesson": _stage("complete" if lesson else "incomplete", [lesson] if lesson else []),
        "evidence_retrieval": _stage("complete" if len(sources) >= 2 else "incomplete", sources),
        "contradiction_search": _stage("complete" if contradiction_search_complete else "incomplete", contradictions),
        "validation": _stage("complete" if validation_passed else "incomplete", abstraction.get("evaluations") or {}),
        "adjustment": _stage(
            "complete" if adjustment_complete else "awaiting",
            [adjustment] if adjustment else ["No adjustment required before testing."] if not contradictions else [],
        ),
        "future_observation": _stage("awaiting"),
        "outcome": _stage("awaiting"),
        "confidence_update": _stage("awaiting"),
        "stored_growth": _stage("blocked"),
    }
    return {
        "engine": "learning_engine",
        "version": "2.0",
        "status": status,
        "decision": decision,
        "candidate_lesson": lesson,
        "source_references": sources,
        "contradiction_references": contradictions,
        "reflection": reflection,
        "adjustment": adjustment,
        "future_observations": [],
        "outcome_history": [],
        "confidence": {
            "current": initial_confidence,
            "trajectory": [{
                "at": _now(),
                "stage": "validation",
                "confidence": initial_confidence,
                "basis": f"{len(sources)} independent sources; {len(contradictions)} contradictions.",
            }],
        },
        "stages": stages,
        "auto_promoted": False,
        "stored_growth": False,
        "instruction": (
            "Wait for a traceable future observation and outcome. Update confidence from "
            "the outcome, then require explicit Doug approval before durable storage."
        ),
    }


def record_learning_outcome(
    learning_cycle: dict,
    observation: str,
    outcome: str,
    evidence_reference: str,
) -> dict:
    """Apply one real future observation and make a deterministic learning decision."""
    cycle = deepcopy(learning_cycle or {})
    outcome = str(outcome or "").strip().lower()
    observation = " ".join(str(observation or "").split()).strip()[:1600]
    evidence_reference = str(evidence_reference or "").strip()[:500]
    if cycle.get("status") != "awaiting_future_observation":
        return {"engine": "learning_engine", "version": "2.0", "status": "rejected", "reason": "cycle_not_awaiting_observation"}
    if outcome not in OUTCOME_EFFECTS:
        return {"engine": "learning_engine", "version": "2.0", "status": "rejected", "reason": "invalid_outcome"}
    if not observation or not evidence_reference:
        return {"engine": "learning_engine", "version": "2.0", "status": "rejected", "reason": "future_observation_provenance_required"}

    observed_at = _now()
    observation_packet = {
        "observed_at": observed_at,
        "observation": observation,
        "evidence_reference": evidence_reference,
        "outcome": outcome,
    }
    cycle.setdefault("future_observations", []).append(observation_packet)
    cycle.setdefault("outcome_history", []).append({
        "observed_at": observed_at,
        "outcome": outcome,
        "evidence_reference": evidence_reference,
    })
    before = float((cycle.get("confidence") or {}).get("current") or 0.0)
    after = round(max(0.0, min(1.0, before + OUTCOME_EFFECTS[outcome])), 2)
    cycle.setdefault("confidence", {})["current"] = after
    cycle["confidence"].setdefault("trajectory", []).append({
        "at": observed_at,
        "stage": "outcome",
        "outcome": outcome,
        "confidence": after,
        "change": OUTCOME_EFFECTS[outcome],
        "basis": "Confidence changed only from the traceable observed outcome.",
    })
    cycle["stages"]["future_observation"] = _stage("complete", [observation_packet])
    cycle["stages"]["outcome"] = _stage("complete", [outcome])
    cycle["stages"]["confidence_update"] = _stage("complete", [cycle["confidence"]["trajectory"][-1]])

    if outcome == "contradicted":
        cycle["status"] = "no_durable_lesson"
        cycle["decision"] = "no_durable_lesson"
        cycle["stages"]["stored_growth"] = _stage("not_applicable")
    elif outcome == "inconclusive":
        cycle["status"] = "awaiting_future_observation"
        cycle["decision"] = "defer"
        cycle["stages"]["future_observation"]["status"] = "awaiting_more_evidence"
    elif after >= 0.55:
        cycle["status"] = "ready_for_governed_storage"
        cycle["decision"] = "candidate_growth_supported"
        cycle["stages"]["stored_growth"] = _stage("awaiting_doug_approval")
    else:
        cycle["status"] = "awaiting_future_observation"
        cycle["decision"] = "defer"
    return cycle


def build_learning_observation(cognitive_packet: dict) -> dict:
    packet = cognitive_packet or {}
    rike = packet.get("rike") or {}
    abstraction = packet.get("experience_abstraction") or {}
    if not abstraction.get("active"):
        return {
            "engine": "learning_engine", "version": "2.0", "status": "not_required",
            "decision": "no_candidate", "auto_promoted": False, "stored_growth": False,
        }
    return build_learning_cycle(
        abstraction,
        reflection=str(rike.get("rationale_summary") or ""),
    )


def ingest_reflective_observation(reflection_packet: dict) -> dict:
    """Accept Phase 8 observations as candidates, never as automatic learning."""
    reflection = reflection_packet or {}
    if not reflection.get("active"):
        return {
            "engine": "learning_engine",
            "version": "2.0",
            "channel": "reflective_metacognition",
            "status": "not_required",
            "auto_promoted": False,
            "stored_growth": False,
        }
    source_reference = str(reflection.get("source_reference") or "").strip()
    if not source_reference:
        return {
            "engine": "learning_engine",
            "version": "2.0",
            "channel": "reflective_metacognition",
            "status": "rejected",
            "reason": "reflection_provenance_required",
            "auto_promoted": False,
            "stored_growth": False,
        }
    observations = list(dict.fromkeys(
        str(item or "").strip()
        for item in reflection.get("observations_for_learning") or []
        if str(item or "").strip()
    ))
    return {
        "engine": "learning_engine",
        "version": "2.0",
        "channel": "reflective_metacognition",
        "status": "candidate_adjustment" if observations else "observation_recorded",
        "source_reference": source_reference[:500],
        "observations": observations,
        "requires_future_observation": bool(observations),
        "requires_doug_approval_for_storage": True,
        "auto_promoted": False,
        "stored_growth": False,
        "instruction": (
            "A reflection can propose an adjustment but cannot prove one. Route any "
            "candidate through evidence, contradiction, future observation and outcome."
        ),
    }


def promote_experience_principle(
    abstraction_packet: dict,
    authorisation: dict | None = None,
    client=None,
    store_func=None,
) -> dict:
    """Retired Phase 5 shortcut: an observed outcome is now mandatory."""
    return {
        "stored": False,
        "reason": "learning_engine_v2_future_observation_and_outcome_required",
    }


def promote_learning_cycle(
    learning_cycle: dict,
    authorisation: dict | None = None,
    client=None,
    store_func=None,
) -> dict:
    """Store growth after the complete cycle and Doug's explicit approval."""
    cycle = learning_cycle or {}
    if cycle.get("status") == "no_durable_lesson":
        return {"stored": False, "reason": "no_durable_lesson"}
    required = LEARNING_STAGES[:-1]
    stages = cycle.get("stages") or {}
    if cycle.get("status") != "ready_for_governed_storage" or any(
        (stages.get(name) or {}).get("status") != "complete" for name in required
    ):
        return {"stored": False, "reason": "learning_cycle_incomplete"}
    authorisation = authorisation or {}
    if not (
        authorisation.get("approved") is True
        and str(authorisation.get("authority") or "").lower() == "doug"
    ):
        return {"stored": False, "reason": "explicit_doug_approval_required"}

    sources = list(dict.fromkeys(
        str(value or "").strip()
        for value in (
            list(cycle.get("source_references") or [])
            + [item.get("evidence_reference") for item in cycle.get("future_observations") or []]
        )
        if str(value or "").strip()
    ))
    lesson = str(cycle.get("candidate_lesson") or "").strip()
    if not lesson or len(sources) < 3:
        return {"stored": False, "reason": "insufficient_validated_provenance"}
    store = store_func or store_llgr
    candidate = {
        "lesson": lesson,
        "validated": True,
        "evidence": sources,
        "reflection": [cycle.get("reflection")],
        "adjustment": cycle.get("adjustment"),
        "contradiction_count": len(cycle.get("contradiction_references") or []),
        "learning_engine_version": "2.0",
        "outcome_history": cycle.get("outcome_history") or [],
        "confidence_trajectory": (cycle.get("confidence") or {}).get("trajectory") or [],
        "governance": {
            "authorised_by": "Doug",
            "future_outcome_observed": True,
            "full_learning_cycle_complete": True,
        },
    }
    outcomes = []
    for index, source in enumerate(sources):
        source_candidate = deepcopy(candidate)
        if index:
            source_candidate["contradiction_count"] = 0
        outcomes.append(store(source_candidate, source_reference=source, client=client))
    stored = bool(outcomes) and all(
        item.get("stored") or item.get("reason") == "duplicate_source"
        for item in outcomes
    )
    return {
        "stored": stored,
        "reason": "stored_growth" if stored else "learning_store_incomplete",
        "source_count": len(sources),
        "outcomes": outcomes,
    }


__all__ = [
    "build_learning_observation",
    "ingest_reflective_observation",
    "extract_user_learning",
    "record_user_learning",
    "build_learning_cycle",
    "record_learning_outcome",
    "promote_experience_principle",
    "promote_learning_cycle",
    "retrieve_growth_context",
    "retrieve_growth_records",
]
