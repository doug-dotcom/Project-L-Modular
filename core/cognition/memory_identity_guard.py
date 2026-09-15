"""Project L Layer 20: memory identity-reification guard.

A remembered episode, feeling or behaviour is evidence about an event, not a licence
to define Doug's identity. This layer prevents cue-driven memory from converting
single or historical episodes into fixed trait claims. Earlier gates remain ceilings:
identity review can preserve or downgrade permission, never upgrade it.
"""

from __future__ import annotations

import re


MEMORY_IDENTITY_GUARD_VERSION = "1.0"

_IDENTITY_LANGUAGE = (
    "i am", "i'm", "i’m", "i always", "i never", "this is who i am",
    "that's who i am", "that is who i am", "person i am", "my personality",
    "my identity", "i tend to", "i'm the kind of person", "i am the kind of person",
)
_FIXED_TRAIT_TERMS = (
    "always", "never", "naturally", "fundamentally", "inherently", "the kind of person",
    "who you are", "your personality", "your identity", "you are someone who",
)
_EPISODIC_MARKERS = (
    "that day", "that time", "once", "last time", "during", "after", "before",
    "when i", "when you", "in 20", "felt", "feeling", "happened",
)
_CHANGE_MARKERS = (
    "changed", "change", "different now", "no longer", "used to", "formerly",
    "grew", "growth", "now i", "these days", "lately",
)


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _lookup_evidence(rhee_packet: dict | None, source: str) -> dict:
    for row in (rhee_packet or {}).get("evidence") or []:
        if isinstance(row, dict) and _text(row.get("source")) == source:
            return row
    return {}


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = _text(text).casefold()
    return any(term in lowered for term in terms)


def _identity_evidence_count(rhee_packet: dict | None) -> int:
    """Count direct identity-style statements conservatively.

    This is not a pattern score. It only distinguishes a lone episode from repeated,
    directly stated self-description in the retrieved packet.
    """
    count = 0
    for row in (rhee_packet or {}).get("evidence") or []:
        if not isinstance(row, dict):
            continue
        passage = _text(row.get("quote_source"))
        role = _text(row.get("role")).casefold()
        if role == "user" and _has_any(passage, _IDENTITY_LANGUAGE):
            count += 1
    return count


def build_memory_identity_guard_packet(
    message: str,
    cue_packet: dict | None,
    privacy_packet: dict | None,
    rhee_packet: dict | None,
) -> dict:
    """Prevent episodic memory from being reified into a fixed identity claim."""
    cue = cue_packet or {}
    privacy = privacy_packet or {}
    if not cue.get("active") or not privacy.get("active"):
        return {
            "engine": "memory_identity_reification_guard",
            "version": MEMORY_IDENTITY_GUARD_VERSION,
            "active": False,
            "decision": "not_required",
            "surface_allowed": False,
            "instruction": "Identity-reification review was not required.",
        }

    prior_decision = str(privacy.get("decision") or "discard")
    if prior_decision != "surface" or not privacy.get("surface_allowed"):
        return {
            "engine": "memory_identity_reification_guard",
            "version": MEMORY_IDENTITY_GUARD_VERSION,
            "active": True,
            "decision": prior_decision if prior_decision in {"silent", "discard"} else "silent",
            "surface_allowed": False,
            "source": None,
            "identity_claim_allowed": False,
            "reason": "Earlier gates did not authorise surfacing; identity review cannot upgrade permission.",
            "governance": {"can_upgrade_prior_permission": False},
        }

    source = _text(privacy.get("source"))
    row = _lookup_evidence(rhee_packet, source)
    passage = _text(row.get("quote_source"))
    present_text = _text(message)

    present_invites_identity = _has_any(present_text, _IDENTITY_LANGUAGE)
    memory_is_episodic = _has_any(passage, _EPISODIC_MARKERS)
    memory_has_change = _has_any(passage, _CHANGE_MARKERS)
    memory_uses_fixed_trait_language = _has_any(passage, _FIXED_TRAIT_TERMS)
    direct_identity_records = _identity_evidence_count(rhee_packet)

    identity_claim_allowed = bool(
        present_invites_identity
        and direct_identity_records >= 2
        and not memory_has_change
    )

    if memory_is_episodic and not present_invites_identity:
        decision = "surface"
        surface_allowed = True
        mode = "event_only"
        reason = "The memory may be surfaced only as an event or past state, not as a fixed identity claim."
    elif memory_has_change:
        decision = "surface"
        surface_allowed = True
        mode = "historical_not_current_identity"
        reason = "The memory contains evidence of change; historical behaviour must not define current identity."
    elif memory_uses_fixed_trait_language and not identity_claim_allowed:
        decision = "silent"
        surface_allowed = False
        mode = "identity_reification_blocked"
        reason = "The memory risks converting limited evidence into a fixed trait without enough current direct support."
    else:
        decision = "surface"
        surface_allowed = True
        mode = "bounded_description"
        reason = "The memory can be used as bounded context without turning it into a fixed identity statement."

    return {
        "engine": "memory_identity_reification_guard",
        "version": MEMORY_IDENTITY_GUARD_VERSION,
        "active": True,
        "decision": decision,
        "surface_allowed": surface_allowed,
        "source": source if surface_allowed else None,
        "identity_claim_allowed": identity_claim_allowed,
        "mode": mode,
        "present_invites_identity": present_invites_identity,
        "memory_is_episodic": memory_is_episodic,
        "memory_has_change": memory_has_change,
        "direct_identity_records": direct_identity_records,
        "reason": reason,
        "instruction": (
            "Do not turn a remembered event, emotion or behaviour into a fixed identity claim. Say what happened, "
            "what Doug felt, or what he did in that context. Use trait or identity language only when the present "
            "question explicitly asks about identity and multiple direct Doug-authored identity statements support it. "
            "Historical identity must not override newer evidence of change. Earlier memory gates remain ceilings."
        ),
        "governance": {
            "can_upgrade_prior_permission": False,
            "episode_is_not_identity": True,
            "past_state_is_not_fixed_trait": True,
            "identity_requires_repeated_direct_evidence": True,
            "current_identity_outranks_history": True,
            "change_evidence_blocks_historical_reification": True,
        },
    }


__all__ = ["MEMORY_IDENTITY_GUARD_VERSION", "build_memory_identity_guard_packet"]
