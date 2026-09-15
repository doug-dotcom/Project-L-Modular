"""Project L Layer 22: memory causal-attribution guard.

Associative memory must not turn sequence, correlation, co-occurrence or emotional
proximity into a causal explanation. This layer preserves earlier publication
ceilings and allows causal use only when retrieved evidence itself directly
attributes a cause. Otherwise a memory may remain contextual, but not causal.
"""

from __future__ import annotations

import re


MEMORY_CAUSAL_ATTRIBUTION_VERSION = "1.0"

_CAUSAL_QUERY = (
    "why did", "why does", "why do", "what caused", "cause of", "because of",
    "reason for", "reason why", "what made", "led to", "triggered",
)
_DIRECT_CAUSAL = (
    "because", "caused by", "the cause was", "the reason was", "the reason i",
    "due to", "resulted from", "happened because", "led directly to",
)
_SEQUENCE_ONLY = (
    "after", "before", "then", "when", "around the same time", "while",
    "during", "followed by", "later", "subsequently",
)


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _lookup_evidence(rhee_packet: dict | None, source: str) -> dict:
    for row in (rhee_packet or {}).get("evidence") or []:
        if isinstance(row, dict) and _text(row.get("source")) == source:
            return row
    return {}


def build_memory_causal_attribution_packet(
    message: str,
    cue_packet: dict | None,
    salience_packet: dict | None,
    rhee_packet: dict | None,
) -> dict:
    """Prevent associative memory from becoming an unsupported causal story."""
    cue = cue_packet or {}
    prior = salience_packet or {}
    if not cue.get("active") or not prior.get("active"):
        return {
            "engine": "memory_causal_attribution_guard",
            "version": MEMORY_CAUSAL_ATTRIBUTION_VERSION,
            "active": False,
            "decision": "not_required",
            "surface_allowed": False,
            "instruction": "Memory causal-attribution review was not required.",
        }

    prior_decision = str(prior.get("decision") or "discard")
    if prior_decision != "surface" or not prior.get("surface_allowed"):
        return {
            "engine": "memory_causal_attribution_guard",
            "version": MEMORY_CAUSAL_ATTRIBUTION_VERSION,
            "active": True,
            "decision": prior_decision if prior_decision in {"silent", "discard"} else "silent",
            "surface_allowed": False,
            "source": None,
            "reason": "Earlier gates did not authorise surfacing; causal review cannot upgrade permission.",
            "governance": {"can_upgrade_prior_permission": False},
        }

    source = _text(prior.get("source"))
    row = _lookup_evidence(rhee_packet, source)
    passage = _text(row.get("quote_source"))
    message_text = _text(message).casefold()
    passage_text = passage.casefold()
    role = _text(row.get("role")).casefold()

    causal_question = any(signal in message_text for signal in _CAUSAL_QUERY)
    direct_causal_language = any(signal in passage_text for signal in _DIRECT_CAUSAL)
    sequence_language = any(
        re.search(rf"\b{re.escape(signal)}\b", passage_text)
        for signal in _SEQUENCE_ONLY
    )
    direct_user_attribution = bool(role == "user" and direct_causal_language)

    if causal_question and not direct_user_attribution:
        decision = "silent"
        surface_allowed = False
        mode = "cause_not_established"
        reason = (
            "The present turn invites a causal explanation, but the retrieved memory does not contain "
            "a direct Doug-authored causal attribution. Sequence or co-occurrence is not enough."
        )
    else:
        decision = "surface"
        surface_allowed = True
        mode = "direct_cause_supported" if direct_user_attribution else "noncausal_context"
        reason = (
            "The retrieved memory contains direct Doug-authored causal attribution."
            if direct_user_attribution else
            "No causal conclusion is required; the memory may be used only for its supported noncausal context."
        )

    return {
        "engine": "memory_causal_attribution_guard",
        "version": MEMORY_CAUSAL_ATTRIBUTION_VERSION,
        "active": True,
        "decision": decision,
        "surface_allowed": surface_allowed,
        "source": source if surface_allowed else None,
        "mode": mode,
        "causal_question": causal_question,
        "direct_causal_language": direct_causal_language,
        "direct_user_attribution": direct_user_attribution,
        "sequence_language": sequence_language,
        "reason": reason,
        "instruction": (
            "Never infer that one event caused another merely because they happened close together, in sequence, "
            "or during the same emotional period. Treat sequence and correlation as context only. A personal causal "
            "claim requires direct supporting attribution in retrieved evidence. If direct causal support is absent, "
            "do not surface the associative memory as an explanation for why something happened. Earlier gates remain "
            "authoritative ceilings, and this layer can never upgrade permission."
        ),
        "governance": {
            "can_upgrade_prior_permission": False,
            "sequence_is_not_causation": True,
            "correlation_is_not_causation": True,
            "emotional_proximity_is_not_causation": True,
            "direct_personal_cause_requires_user_attribution": True,
            "context_may_be_preserved_without_causal_claim": True,
        },
    }


__all__ = ["MEMORY_CAUSAL_ATTRIBUTION_VERSION", "build_memory_causal_attribution_packet"]
