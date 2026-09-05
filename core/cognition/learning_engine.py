"""Canonical, provenance-gated Project L learning engine.

Legacy Allegra storage remains as a compatibility datastore, but no autonomous
agent infers lessons from L's own replies. Only explicit Doug-authored learning
observations become candidates, and retrieval applies the existing independent-
source and contradiction thresholds.
"""

from __future__ import annotations

import re

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


def build_learning_observation(cognitive_packet: dict) -> dict:
    rike = (cognitive_packet or {}).get("rike") or {}
    abstraction = (cognitive_packet or {}).get("experience_abstraction") or {}
    return {
        "engine": "learning_engine",
        "version": "1.0",
        "status": "awaiting_outcome",
        "auto_promoted": False,
        "reason": "A reasoning output is not proof of learning; an observed outcome or explicit Doug-authored lesson is required.",
        "reasoning_status": rike.get("status", "unknown"),
        "experience_abstraction_status": abstraction.get("status", "not_evaluated"),
    }


def promote_experience_principle(
    abstraction_packet: dict,
    authorisation: dict | None = None,
    client=None,
    store_func=None,
) -> dict:
    """Persist a validated principle only after explicit Doug authorisation."""
    packet = abstraction_packet or {}
    governance = packet.get("governance") or {}
    evaluations = packet.get("evaluations") or {}
    validation_chain_passed = all(
        (evaluations.get(stage) or {}).get("passed") is True
        for stage in ("rhee", "quinn", "rike", "mary")
    )
    authorisation = authorisation or {}
    if not governance.get("promotion_eligible") or not validation_chain_passed:
        return {"stored": False, "reason": "abstraction_not_eligible"}
    if not (
        authorisation.get("approved") is True
        and str(authorisation.get("authority") or "").lower() == "doug"
    ):
        return {"stored": False, "reason": "explicit_doug_approval_required"}
    lesson = str(packet.get("candidate_principle") or "").strip()
    sources = list(packet.get("source_references") or [])
    if not lesson or len(set(sources)) < 2:
        return {"stored": False, "reason": "insufficient_validated_provenance"}

    store = store_func or store_llgr
    outcomes = []
    candidate = {
        "lesson": lesson,
        "validated": True,
        "evidence": sources,
        "reflection": ["Phase 5 governed experience abstraction"],
        "contradiction_count": len(packet.get("contradiction_references") or []),
        "abstraction_version": packet.get("version", "1.0"),
        "governance": {
            "authorised_by": "Doug",
            "quinn_reviewed": True,
            "rike_challenged": True,
            "mary_validated": True,
        },
    }
    for source in dict.fromkeys(sources):
        outcomes.append(store(candidate, source_reference=source, client=client))
    return {
        "stored": any(item.get("stored") for item in outcomes),
        "reason": "governed_principle_promoted",
        "source_count": len(set(sources)),
        "outcomes": outcomes,
    }


__all__ = [
    "build_learning_observation",
    "extract_user_learning",
    "record_user_learning",
    "promote_experience_principle",
    "retrieve_growth_context",
    "retrieve_growth_records",
]
