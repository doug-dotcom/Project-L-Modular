"""Project L Layer 16: memory counterexample and anti-confirmation guard.

Associative retrieval must not let one vivid or convenient memory become proof of
a general story. This layer checks the already-retrieved evidence for materially
similar experiences with different outcomes, explicit contradictions, or
qualifying exceptions before a memory is allowed to shape a conclusion.
"""

from __future__ import annotations

import re


MEMORY_COUNTEREXAMPLE_VERSION = "1.0"
MAX_COUNTEREXAMPLES = 4

_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has",
    "had", "was", "were", "are", "is", "you", "your", "me", "my", "i",
    "it", "to", "of", "in", "on", "at", "a", "an", "as", "but", "or",
    "feel", "feeling", "felt", "again", "before", "same", "thing",
}
_POSITIVE = (
    "worked", "helped", "better", "improved", "calm", "relaxed", "successful",
    "success", "good", "easier", "resolved", "finished", "completed",
)
_NEGATIVE = (
    "didn't work", "did not work", "worse", "failed", "failure", "harder",
    "stuck", "problem", "hurt", "pain", "overwhelmed", "didn't help",
    "did not help", "not better", "unfinished",
)
_CONTRADICTION = (
    "not always", "except", "however", "although", "but this time", "different",
    "opposite", "contradiction", "contradicted", "didn't", "did not", "wasn't",
    "was not", "no longer",
)


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _terms(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9']+", _text(value).casefold())
        if len(token) >= 3 and token not in _STOP
    }


def _overlap(left: str, right: str) -> float:
    a, b = _terms(left), _terms(right)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, min(len(a), 8))


def _polarity(value: str) -> str:
    text = _text(value).casefold()
    positive = any(item in text for item in _POSITIVE)
    negative = any(item in text for item in _NEGATIVE)
    if positive and not negative:
        return "positive"
    if negative and not positive:
        return "negative"
    if positive and negative:
        return "mixed"
    return "unknown"


def _lookup_evidence(rhee_packet: dict | None, source: str) -> dict:
    for row in (rhee_packet or {}).get("evidence") or []:
        if isinstance(row, dict) and _text(row.get("source")) == source:
            return row
    return {}


def build_memory_counterexample_packet(
    message: str,
    cue_packet: dict | None,
    value_packet: dict | None,
    rhee_packet: dict | None,
) -> dict:
    """Check whether a surfaceable associative memory has meaningful counterevidence.

    Earlier gates remain ceilings: this layer can preserve or downgrade surface
    permission but can never promote a silent/discarded memory.
    """
    cue = cue_packet or {}
    value = value_packet or {}
    if not cue.get("active") or not value.get("active"):
        return {
            "engine": "memory_counterexample_guard",
            "version": MEMORY_COUNTEREXAMPLE_VERSION,
            "active": False,
            "decision": "not_required",
            "surface_allowed": False,
            "instruction": "Counterexample review was not required.",
        }

    prior_decision = str(value.get("decision") or "discard")
    if prior_decision != "surface" or not value.get("surface_allowed"):
        return {
            "engine": "memory_counterexample_guard",
            "version": MEMORY_COUNTEREXAMPLE_VERSION,
            "active": True,
            "decision": prior_decision if prior_decision in {"silent", "discard"} else "silent",
            "surface_allowed": False,
            "counterexamples": [],
            "reason": "Earlier gates did not authorise surfacing; anti-confirmation review cannot upgrade permission.",
            "governance": {"can_upgrade_prior_permission": False},
        }

    source = _text(value.get("source"))
    winner = _lookup_evidence(rhee_packet, source)
    winner_passage = _text(winner.get("quote_source"))
    winner_polarity = _polarity(winner_passage)

    candidates = []
    for row in (rhee_packet or {}).get("evidence") or []:
        if not isinstance(row, dict):
            continue
        other_source = _text(row.get("source"))
        if not other_source or other_source == source:
            continue
        passage = _text(row.get("quote_source"))
        if not passage:
            continue
        overlap = _overlap(winner_passage or message, passage)
        present_overlap = _overlap(message, passage)
        polarity = _polarity(passage)
        explicit_contradiction = any(term in passage.casefold() for term in _CONTRADICTION)
        opposite_outcome = (
            winner_polarity in {"positive", "negative"}
            and polarity in {"positive", "negative"}
            and winner_polarity != polarity
        )
        if overlap >= 0.2 and (opposite_outcome or explicit_contradiction):
            candidates.append({
                "source": other_source,
                "topic_overlap": round(overlap, 2),
                "present_overlap": round(present_overlap, 2),
                "polarity": polarity,
                "opposite_outcome": opposite_outcome,
                "explicit_contradiction": explicit_contradiction,
            })

    candidates.sort(
        key=lambda item: (item["present_overlap"], item["topic_overlap"]),
        reverse=True,
    )
    counterexamples = candidates[:MAX_COUNTEREXAMPLES]
    material_counterexample = any(
        item["present_overlap"] >= 0.18 and item["topic_overlap"] >= 0.25
        for item in counterexamples
    )

    if material_counterexample:
        decision = "silent"
        surface_allowed = False
        reason = (
            "A materially similar retrieved experience points to a different outcome or explicit qualification; "
            "one associative memory must not be surfaced as a general rule."
        )
    else:
        decision = "surface"
        surface_allowed = True
        reason = "No material counterexample was found in the bounded retrieved evidence."

    return {
        "engine": "memory_counterexample_guard",
        "version": MEMORY_COUNTEREXAMPLE_VERSION,
        "active": True,
        "decision": decision,
        "surface_allowed": surface_allowed,
        "source": source if surface_allowed else None,
        "winner_polarity": winner_polarity,
        "counterexamples": counterexamples,
        "material_counterexample_found": material_counterexample,
        "reason": reason,
        "instruction": (
            "Do not let a single retrieved memory become evidence for a general pattern when similarly relevant "
            "retrieved experiences point the other way. If a material counterexample exists, keep the original "
            "memory silent unless Doug explicitly asks to compare experiences. Preserve exceptions and mixed "
            "outcomes rather than forcing consistency. Absence of a counterexample in this bounded packet is not "
            "proof that none exists."
        ),
        "governance": {
            "can_upgrade_prior_permission": False,
            "single_memory_is_not_pattern": True,
            "counterexamples_must_be_preserved": True,
            "absence_of_counterexample_is_not_proof": True,
            "confirmation_bias_guard": True,
            "bounded_retrieval_acknowledged": True,
        },
    }


__all__ = ["MEMORY_COUNTEREXAMPLE_VERSION", "build_memory_counterexample_packet"]
