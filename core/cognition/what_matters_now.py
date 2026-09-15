"""Project L Layer 10: bounded whole-life priority synthesis.

This layer answers "what matters now?" by ranking already-governed signals from
L's current cognitive packet. It does not create obligations, infer urgency from
emotion, or decide for Doug. At most three priorities are surfaced and each must
retain a visible evidence basis.
"""

from __future__ import annotations

import re


WHAT_MATTERS_NOW_VERSION = "1.0"
MAX_PRIORITIES = 3


def what_matters_now_requested(message: str) -> bool:
    text = " ".join(str(message or "").lower().split())
    return any(signal in text for signal in (
        "what matters now",
        "what matters most",
        "what should i focus on",
        "what should i focus on now",
        "what deserves my attention",
        "what needs my attention",
        "top priorities",
        "my priorities right now",
        "priorities right now",
        "biggest priorities",
        "most important things right now",
        "what are the three things",
        "what are the 3 things",
        "what should i be paying attention to",
    ))


def _clip(value: object, limit: int = 420) -> str:
    return " ".join(str(value or "").split())[:limit]


def _candidate(kind: str, text: str, score: float, basis: str, evidence_refs=None) -> dict:
    return {
        "kind": kind,
        "text": _clip(text),
        "score": round(max(0.0, min(1.0, float(score))), 2),
        "basis": _clip(basis, 320),
        "evidence_refs": list(evidence_refs or [])[:6],
        "is_obligation": False,
    }


def _dedupe(candidates: list[dict]) -> list[dict]:
    result = []
    seen = set()
    for item in candidates:
        key = re.sub(r"[^a-z0-9]+", " ", item.get("text", "").lower()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def build_what_matters_now_packet(
    message: str,
    working_memory: dict | None,
    mary_packet: dict | None,
    anticipation_packet: dict | None,
    timeline_packet: dict | None,
    relationship_packet: dict | None,
    research_packet: dict | None,
    confidence_evidence_packet: dict | None,
) -> dict:
    requested = what_matters_now_requested(message)
    if not requested:
        return {
            "engine": "what_matters_now_layer",
            "version": WHAT_MATTERS_NOW_VERSION,
            "active": False,
            "priorities": [],
            "instruction": "Whole-life priority synthesis was not requested.",
            "governance": {
                "max_priorities": MAX_PRIORITIES,
                "doug_retains_agency": True,
                "autonomous_actions": False,
            },
        }

    working = working_memory or {}
    mary = mary_packet or {}
    anticipation = anticipation_packet or {}
    timeline = timeline_packet or {}
    relationship = relationship_packet or {}
    research = research_packet or {}
    confidence = confidence_evidence_packet or {}
    candidates: list[dict] = []

    # Explicit unfinished work has the strongest claim on current attention.
    unresolved = [
        _clip(item) for item in (working.get("unresolved_questions") or []) if _clip(item)
    ]
    if unresolved:
        candidates.append(_candidate(
            "unfinished_commitment",
            unresolved[-1],
            0.94,
            "Explicit unresolved thread in current working context.",
        ))

    # An anticipation candidate is only eligible if the anticipation layer itself
    # considered it surfaceable; we never inflate weak anticipation here.
    for item in anticipation.get("candidates") or []:
        try:
            confidence_score = float(item.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence_score = 0.0
        if confidence_score >= 0.75:
            candidates.append(_candidate(
                "near_term_follow_through",
                item.get("text"),
                min(0.9, confidence_score),
                item.get("basis") or "High-confidence anticipated next need.",
            ))

    # Current governed patterns can matter, but only after Mary's pattern gate.
    if (
        mary.get("active")
        and mary.get("pattern_threshold_met") is True
        and mary.get("current_relevance") == "current"
    ):
        candidates.append(_candidate(
            "current_pattern",
            mary.get("pattern_query") or "Current life pattern",
            0.78,
            "Current longitudinal pattern passed Mary's corroboration threshold.",
            mary.get("evidence_refs") or [],
        ))

    # Timeline turning points are context, not automatically current priorities.
    # Only the most recent dated turning point is eligible and with lower weight.
    turning_points = list(timeline.get("turning_points") or [])
    if timeline.get("active") and turning_points:
        latest = turning_points[-1]
        candidates.append(_candidate(
            "recent_turning_point",
            latest.get("summary") or latest.get("text") or latest.get("event") or "Recent turning point",
            0.7,
            "Recent dated turning point may shape what deserves attention now.",
            [latest.get("evidence_ref")] if latest.get("evidence_ref") else [],
        ))

    # Explicit unresolved relationship threads can be relevant, but relationship
    # importance is never inferred merely from frequency or emotional wording.
    rel_threads = relationship.get("unresolved_threads") or []
    if relationship.get("active") and rel_threads:
        candidates.append(_candidate(
            "relationship_thread",
            rel_threads[-1] if isinstance(rel_threads[-1], str) else rel_threads[-1].get("summary", "Relationship thread"),
            0.76,
            "Explicit unresolved relationship thread in governed relationship evidence.",
            relationship.get("evidence_refs") or [],
        ))

    # Research unknowns matter only when Doug is actively carrying a research task.
    if research.get("active"):
        unknowns = research.get("unknowns") or []
        if unknowns:
            item = unknowns[0]
            candidates.append(_candidate(
                "research_gap",
                item if isinstance(item, str) else item.get("text", "Research evidence gap"),
                0.72,
                "Open evidence gap in an active personal research brief.",
                research.get("evidence_refs") or [],
            ))

    candidates = _dedupe(sorted(candidates, key=lambda item: item["score"], reverse=True))

    # If factual confidence is materially weak, do not manufacture a ranked life
    # plan from thin evidence. Current explicit working-memory commitments may still
    # survive because they are direct operational context.
    claim_policy = confidence.get("claim_policy") or {}
    fact_allowed = bool(claim_policy.get("fact_allowed", True))
    if not fact_allowed:
        candidates = [item for item in candidates if item["kind"] == "unfinished_commitment"]

    priorities = candidates[:MAX_PRIORITIES]
    return {
        "engine": "what_matters_now_layer",
        "version": WHAT_MATTERS_NOW_VERSION,
        "active": True,
        "priorities": priorities,
        "priority_count": len(priorities),
        "instruction": (
            "Answer Doug with at most three things that most deserve attention now. Present them as "
            "a grounded synthesis, not commands. Explain briefly why each matters using only the supplied "
            "basis. Preserve Doug's agency: he can choose a different priority. Do not infer urgency from "
            "emotion, repetition, or frequency alone. If evidence is too weak, say the picture is not clear "
            "enough rather than inventing a priority."
        ),
        "governance": {
            "max_priorities": MAX_PRIORITIES,
            "doug_retains_agency": True,
            "autonomous_actions": False,
            "emotion_does_not_equal_urgency": True,
            "frequency_does_not_equal_importance": True,
            "missing_evidence_can_result_in_no_priority": True,
        },
    }


__all__ = [
    "WHAT_MATTERS_NOW_VERSION",
    "MAX_PRIORITIES",
    "what_matters_now_requested",
    "build_what_matters_now_packet",
]
