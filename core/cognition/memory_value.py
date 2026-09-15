"""Project L Layer 15: memory value-of-information gate.

A memory can be relevant, well sourced and unambiguous while still adding
nothing useful to the present answer. This layer estimates incremental value:
would using the memory materially improve understanding, choice, continuity or
support? It may only preserve or downgrade prior publication permission; it can
never upgrade a memory that earlier gates kept silent or discarded.
"""

from __future__ import annotations

import re


MEMORY_VALUE_VERSION = "1.0"

_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has",
    "had", "was", "were", "are", "is", "you", "your", "me", "my", "i",
    "it", "to", "of", "in", "on", "at", "a", "an", "as", "but", "or",
    "feel", "feeling", "felt", "again", "before", "same", "thing",
}
_ADVICE_SIGNALS = (
    "what should", "what do you think", "what would you", "how should",
    "what can i", "help me", "any advice", "what now", "what next",
)
_DECISION_SIGNALS = (
    "decide", "decision", "choose", "choice", "option", "go with", "pick",
)
_LESSON_SIGNALS = (
    "learned", "learnt", "realised", "realized", "helped", "worked",
    "didn't work", "did not work", "lesson", "because", "reason", "instead",
)
_CONTINUITY_SIGNALS = (
    "again", "like before", "same thing", "same feeling", "keeps happening",
    "keeps coming up", "reminds me", "here we go again",
)


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _terms(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9']+", _text(value).casefold())
        if len(token) >= 3 and token not in _STOP
    }


def _lookup_evidence(rhee_packet: dict | None, source: str) -> dict:
    for row in (rhee_packet or {}).get("evidence") or []:
        if isinstance(row, dict) and _text(row.get("source")) == source:
            return row
    return {}


def _novelty(message: str, passage: str) -> float:
    present = _terms(message)
    memory = _terms(passage)
    if not memory:
        return 0.0
    novel = memory - present
    return round(min(1.0, len(novel) / max(1, min(len(memory), 12))), 2)


def build_memory_value_packet(
    message: str,
    cue_packet: dict | None,
    relevance_packet: dict | None,
    contrast_packet: dict | None,
    rhee_packet: dict | None,
) -> dict:
    """Decide whether an already-authorised memory adds enough value to mention.

    The score is a materiality heuristic, never a truth probability. Earlier
    relevance/contrast decisions are authoritative ceilings: this layer cannot
    turn silent or discarded memory into surfaceable memory.
    """
    cue = cue_packet or {}
    relevance = relevance_packet or {}
    contrast = contrast_packet or {}

    if not cue.get("active") or not contrast.get("active"):
        return {
            "engine": "memory_value_of_information",
            "version": MEMORY_VALUE_VERSION,
            "active": False,
            "decision": "not_required",
            "surface_allowed": False,
            "instruction": "Memory value-of-information review was not required.",
        }

    prior_decision = str(contrast.get("decision") or relevance.get("decision") or "discard")
    if prior_decision != "surface" or not contrast.get("surface_allowed"):
        return {
            "engine": "memory_value_of_information",
            "version": MEMORY_VALUE_VERSION,
            "active": True,
            "decision": prior_decision if prior_decision in {"silent", "discard"} else "silent",
            "surface_allowed": False,
            "prior_permission": prior_decision,
            "expected_answer_delta": "none",
            "reason": "Earlier relevance or contrast gates did not authorise surfacing; this layer cannot upgrade permission.",
            "governance": {
                "can_upgrade_prior_permission": False,
                "relevance_is_not_utility": True,
                "truth_probability_score": False,
            },
        }

    source = _text(contrast.get("winner"))
    row = _lookup_evidence(rhee_packet, source)
    passage = _text(row.get("quote_source"))
    lowered_message = _text(message).casefold()
    lowered_passage = passage.casefold()

    novelty = _novelty(message, passage)
    asks_advice = any(signal in lowered_message for signal in _ADVICE_SIGNALS)
    decision_context = any(signal in lowered_message for signal in _DECISION_SIGNALS)
    continuity_context = any(signal in lowered_message for signal in _CONTINUITY_SIGNALS)
    memory_has_lesson = any(signal in lowered_passage for signal in _LESSON_SIGNALS)
    memory_has_decision = any(signal in lowered_passage for signal in _DECISION_SIGNALS)

    utility = 0.0
    reasons = []

    # The memory must add something beyond merely echoing the present turn.
    utility += 0.22 * novelty
    if novelty >= 0.35:
        reasons.append("adds_new_context")

    if asks_advice and (memory_has_lesson or memory_has_decision):
        utility += 0.38
        reasons.append("prior_experience_can_change_guidance")
    elif decision_context and memory_has_decision:
        utility += 0.32
        reasons.append("prior_decision_can_change_choice_context")

    if continuity_context and (memory_has_lesson or memory_has_decision):
        utility += 0.26
        reasons.append("recurring_context_has_prior_learning")

    # Strong relevance can justify a modest continuity benefit, but not by
    # itself enough to surface a redundant memory.
    top_relevance = max(
        [float(item.get("relevance") or 0.0) for item in relevance.get("surface") or []]
        or [0.0]
    )
    utility += 0.14 * min(1.0, top_relevance)

    utility = round(min(1.0, utility), 2)
    if utility >= 0.58:
        decision = "surface"
        surface_allowed = True
        delta = "material"
        reason = "The memory is expected to materially improve the present answer rather than merely repeat it."
    elif utility >= 0.34:
        decision = "silent"
        surface_allowed = False
        delta = "modest"
        reason = "The memory may improve reasoning slightly, but mentioning it would add more clutter than value."
    else:
        decision = "discard"
        surface_allowed = False
        delta = "negligible"
        reason = "The memory is relevant but largely redundant or non-actionable for this turn."

    return {
        "engine": "memory_value_of_information",
        "version": MEMORY_VALUE_VERSION,
        "active": True,
        "decision": decision,
        "surface_allowed": surface_allowed,
        "source": source if surface_allowed else None,
        "prior_permission": prior_decision,
        "utility": utility,
        "novelty": novelty,
        "expected_answer_delta": delta,
        "signals": {
            "asks_advice": asks_advice,
            "decision_context": decision_context,
            "continuity_context": continuity_context,
            "memory_has_lesson": memory_has_lesson,
            "memory_has_decision": memory_has_decision,
        },
        "reasons": reasons,
        "reason": reason,
        "instruction": (
            "Use this as the final usefulness gate for cue-driven memory. A memory may be accurate, "
            "relevant and unambiguous yet still not deserve mention. Surface it only when doing so "
            "materially improves Doug's present understanding, decision, continuity or support. "
            "If it merely repeats what Doug just said, keep it silent or discard it. Never announce "
            "this scoring process, and never treat the utility score as confidence or truth."
        ),
        "governance": {
            "can_upgrade_prior_permission": False,
            "relevance_is_not_utility": True,
            "redundant_memory_should_not_surface": True,
            "material_answer_change_required": True,
            "silent_use_preferred_over_clutter": True,
            "truth_probability_score": False,
        },
    }


__all__ = ["MEMORY_VALUE_VERSION", "build_memory_value_packet"]
