"""Project L Layer 21: memory emotional-salience guard.

Emotionally intense memories are cognitively sticky. They must not outrank quieter,
more relevant evidence merely because they are vivid. This layer runs after the
identity guard and may preserve or downgrade permission, never upgrade it.
"""

from __future__ import annotations

import re


MEMORY_EMOTIONAL_SALIENCE_VERSION = "1.0"

_HIGH_SALIENCE = (
    "terrified", "devastated", "furious", "panic", "panicked", "nightmare",
    "trauma", "abuse", "abandoned", "betrayed", "heartbroken", "overwhelmed",
    "ashamed", "guilty", "suicidal", "self-harm", "relapse", "hospital",
)
_MODERATE_SALIENCE = (
    "worried", "anxious", "angry", "sad", "scared", "upset", "stressed",
    "frustrated", "hurt", "afraid", "guilt", "shame",
)
_EMOTION_INVITATION = (
    "how did i feel", "what was i feeling", "emotion", "emotional", "why was i so",
    "what upset me", "what scared me", "what worried me", "what hurt me",
    "remind me how i felt", "talk about how i felt",
)
_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "had",
    "was", "were", "are", "is", "you", "your", "me", "my", "i", "it", "to",
    "of", "in", "on", "at", "a", "an", "as", "but", "or",
}


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


def _salience(value: str) -> float:
    text = _text(value).casefold()
    high = sum(1 for item in _HIGH_SALIENCE if item in text)
    moderate = sum(1 for item in _MODERATE_SALIENCE if item in text)
    return round(min(1.0, 0.34 * high + 0.16 * moderate), 2)


def _lookup(rhee_packet: dict | None, source: str) -> dict:
    for row in (rhee_packet or {}).get("evidence") or []:
        if isinstance(row, dict) and _text(row.get("source")) == source:
            return row
    return {}


def build_memory_emotional_salience_packet(
    message: str,
    cue_packet: dict | None,
    identity_packet: dict | None,
    rhee_packet: dict | None,
) -> dict:
    """Prevent vivid memory from winning purely because it is emotionally intense."""
    cue = cue_packet or {}
    identity = identity_packet or {}
    if not cue.get("active") or not identity.get("active"):
        return {
            "engine": "memory_emotional_salience_guard",
            "version": MEMORY_EMOTIONAL_SALIENCE_VERSION,
            "active": False,
            "decision": "not_required",
            "surface_allowed": False,
            "instruction": "Emotional-salience review was not required.",
        }

    prior_decision = str(identity.get("decision") or "discard")
    if prior_decision != "surface" or not identity.get("surface_allowed"):
        return {
            "engine": "memory_emotional_salience_guard",
            "version": MEMORY_EMOTIONAL_SALIENCE_VERSION,
            "active": True,
            "decision": prior_decision if prior_decision in {"silent", "discard"} else "silent",
            "surface_allowed": False,
            "reason": "Earlier gates did not authorise surfacing; salience review cannot upgrade permission.",
            "governance": {"can_upgrade_prior_permission": False},
        }

    source = _text(identity.get("source"))
    row = _lookup(rhee_packet, source)
    passage = _text(row.get("quote_source"))
    salience = _salience(passage)
    present_salience = _salience(message)
    lowered = _text(message).casefold()
    emotion_invited = any(signal in lowered for signal in _EMOTION_INVITATION)

    quieter_competitor = None
    best_quieter_overlap = 0.0
    for other in (rhee_packet or {}).get("evidence") or []:
        if not isinstance(other, dict):
            continue
        other_source = _text(other.get("source"))
        if not other_source or other_source == source:
            continue
        other_passage = _text(other.get("quote_source"))
        other_salience = _salience(other_passage)
        overlap = _overlap(message, other_passage)
        if other_salience + 0.25 < salience and overlap >= 0.22 and overlap > best_quieter_overlap:
            best_quieter_overlap = overlap
            quieter_competitor = other_source

    if salience >= 0.5 and quieter_competitor and not emotion_invited and present_salience < 0.35:
        decision = "silent"
        surface_allowed = False
        reason = (
            "The candidate memory is highly emotional while a quieter similarly relevant memory exists; "
            "vividness must not decide what gets surfaced."
        )
        mode = "salience_downweighted"
    else:
        decision = "surface"
        surface_allowed = True
        reason = (
            "Emotional intensity does not appear to be distorting selection, or the present turn explicitly invites emotional recall."
        )
        mode = "salience_acceptable"

    return {
        "engine": "memory_emotional_salience_guard",
        "version": MEMORY_EMOTIONAL_SALIENCE_VERSION,
        "active": True,
        "decision": decision,
        "surface_allowed": surface_allowed,
        "source": source if surface_allowed else None,
        "mode": mode,
        "memory_salience": salience,
        "present_salience": present_salience,
        "emotion_invited": emotion_invited,
        "quieter_competitor": quieter_competitor,
        "quieter_competitor_overlap": round(best_quieter_overlap, 2),
        "reason": reason,
        "instruction": (
            "Do not privilege a memory because it is emotionally vivid. Emotional intensity is not relevance, truth, "
            "importance or priority. Prefer quieter evidence when it fits the present turn equally well or better. "
            "If Doug explicitly asks about the emotional experience, the vivid memory may be surfaced subject to all "
            "earlier gates. Never dramatise a memory merely because its wording is intense."
        ),
        "governance": {
            "can_upgrade_prior_permission": False,
            "emotional_intensity_is_not_importance": True,
            "emotional_intensity_is_not_truth": True,
            "quieter_evidence_must_compete": True,
            "emotion_can_surface_when_explicitly_invited": True,
            "dramatisation_prohibited": True,
        },
    }


__all__ = ["MEMORY_EMOTIONAL_SALIENCE_VERSION", "build_memory_emotional_salience_packet"]
