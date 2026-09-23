"""Project L Layer 3: bounded anticipation without autonomous action.

Anticipation prepares likely next needs from already-governed context. It never
creates facts, performs actions, or interrupts Doug with speculative prompts.
Only high-confidence, immediately useful candidates may be surfaced by L.
"""

from __future__ import annotations


ANTICIPATION_VERSION = "1.1"
MAX_CANDIDATES = 3


def _clip(value: object, limit: int = 500) -> str:
    return " ".join(str(value or "").split())[:limit]


def _candidate(kind: str, text: str, confidence: float, basis: str) -> dict:
    return {
        "kind": kind,
        "text": _clip(text),
        "confidence": round(max(0.0, min(1.0, float(confidence))), 2),
        "basis": _clip(basis, 300),
        "action_authority": False,
    }


def build_anticipation_packet(
    message: str,
    working_memory: dict | None,
    mary_packet: dict | None,
    rhee_packet: dict | None,
) -> dict:
    """Return a small inspectable set of likely next needs.

    The layer is intentionally conservative: it uses explicit unresolved work,
    recent decisions and governed longitudinal evidence. It does not infer future
    appointments, emotions, intentions or external events from weak hints.
    """
    working = working_memory or {}
    mary = mary_packet or {}
    rhee = rhee_packet or {}
    candidates: list[dict] = []

    unresolved = [
        _clip(item) for item in (working.get("unresolved_questions") or [])
        if _clip(item)
    ]
    if unresolved:
        candidates.append(_candidate(
            "unfinished_thread",
            unresolved[-1],
            0.9,
            "Explicit unresolved question in active working memory.",
        ))

    decisions = [
        _clip(item) for item in (working.get("recent_decisions") or [])
        if _clip(item)
    ]
    phase = str(working.get("conversation_phase") or "")
    if decisions and phase in {"planning", "execution", "review"}:
        candidates.append(_candidate(
            "decision_follow_through",
            decisions[-1],
            0.78,
            f"Recent explicit decision remains relevant during {phase}.",
        ))

    if (
        mary.get("active")
        and mary.get("pattern_threshold_met") is True
        and mary.get("current_relevance") == "current"
    ):
        support = mary.get("supporting_episodes") or []
        # Mary 5.1 emits a count. Older packets used a nested count object.
        domains = mary.get("cross_domain_support")
        if isinstance(domains, dict):
            domains = domains.get("domain_count")
        # An invalid count must not manufacture cross-domain confidence.
        domain_count = domains if type(domains) is int and domains >= 0 else 0
        if len(support) >= 2:
            candidates.append(_candidate(
                "current_pattern_watch",
                _clip(mary.get("pattern_query") or message),
                0.72 if domain_count >= 2 else 0.66,
                (
                    f"Mary found a current governed pattern with {len(support)} supporting episodes"
                    + (f" across {domain_count} domains." if domain_count else ".")
                ),
            ))

    # Retrieval evidence can justify preparing context, but not inventing a need.
    recall_active = bool(rhee.get("recall_active"))
    if recall_active and not candidates and working.get("current_goal"):
        candidates.append(_candidate(
            "context_ready",
            _clip(working.get("current_goal")),
            0.6,
            "Relevant governed memory was retrieved for the active goal.",
        ))

    candidates = sorted(candidates, key=lambda item: item["confidence"], reverse=True)[:MAX_CANDIDATES]
    surfaceable = [item for item in candidates if item["confidence"] >= 0.75]

    return {
        "engine": "anticipation_layer",
        "version": ANTICIPATION_VERSION,
        "active": bool(candidates),
        "candidates": candidates,
        "surfaceable_count": len(surfaceable),
        "highest_confidence": surfaceable[0]["confidence"] if surfaceable else None,
        "instruction": (
            "Quietly prepare for these possible next needs. Surface at most one only when it is "
            "directly useful to Doug's current turn. Never interrupt an emotional conversation, "
            "never claim a predicted need as fact, never create reminders/actions without Doug's "
            "request, and never mention internal anticipation machinery. If no candidate is clearly "
            "useful, say nothing about it."
            if candidates else
            "No sufficiently grounded next need was identified; do not manufacture one."
        ),
        "governance": {
            "prediction_is_fact": False,
            "autonomous_actions": False,
            "max_surface_per_turn": 1,
            "minimum_surface_confidence": 0.75,
            "silence_is_valid": True,
        },
    }


__all__ = ["ANTICIPATION_VERSION", "build_anticipation_packet"]
