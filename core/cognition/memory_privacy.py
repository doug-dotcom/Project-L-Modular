"""Project L Layer 19: memory privacy and intimacy boundary guard.

A memory may be relevant, current and useful while still being too intimate to
surface unprompted. This layer is the final disclosure boundary for cue-driven
memory. Earlier gates remain ceilings: privacy can preserve or downgrade surface
permission, never upgrade it.
"""

from __future__ import annotations

import re


MEMORY_PRIVACY_VERSION = "1.0"

_HIGH_INTIMACY = {
    "trauma": ("trauma", "abuse", "assault", "neglect", "nightmare"),
    "sexual": ("sexual", "sex life", "hypersexual", "intimate"),
    "mental_health": ("diagnosis", "ptsd", "cptsd", "adhd", "autism", "suicide", "self-harm"),
    "substance_history": ("alcohol use disorder", "addiction", "rehab", "relapse"),
    "legal_financial": ("legal", "solicitor", "claim", "insurance", "debt", "tax debt"),
    "private_relationship": ("breakup", "affair", "private relationship", "intimate relationship"),
}
_DIRECT_INVITATION = (
    "remind me", "what happened", "tell me about", "bring up", "talk about",
    "what did i say", "what do you remember", "recall", "deep recall",
)


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _categories(value: str) -> set[str]:
    text = _text(value).casefold()
    found = set()
    for category, terms in _HIGH_INTIMACY.items():
        if any(term in text for term in terms):
            found.add(category)
    return found


def _lookup_evidence(rhee_packet: dict | None, source: str) -> dict:
    for row in (rhee_packet or {}).get("evidence") or []:
        if isinstance(row, dict) and _text(row.get("source")) == source:
            return row
    return {}


def build_memory_privacy_packet(
    message: str,
    cue_packet: dict | None,
    temporal_packet: dict | None,
    rhee_packet: dict | None,
) -> dict:
    """Apply an intimacy boundary to an already-surfaceable memory."""
    cue = cue_packet or {}
    temporal = temporal_packet or {}
    if not cue.get("active") or not temporal.get("active"):
        return {
            "engine": "memory_privacy_guard",
            "version": MEMORY_PRIVACY_VERSION,
            "active": False,
            "decision": "not_required",
            "surface_allowed": False,
            "instruction": "Memory privacy review was not required.",
        }

    prior_decision = str(temporal.get("decision") or "discard")
    if prior_decision != "surface" or not temporal.get("surface_allowed"):
        return {
            "engine": "memory_privacy_guard",
            "version": MEMORY_PRIVACY_VERSION,
            "active": True,
            "decision": prior_decision if prior_decision in {"silent", "discard"} else "silent",
            "surface_allowed": False,
            "source": None,
            "reason": "Earlier gates did not authorise surfacing; privacy review cannot upgrade permission.",
            "governance": {"can_upgrade_prior_permission": False},
        }

    source = _text(temporal.get("source"))
    row = _lookup_evidence(rhee_packet, source)
    passage = _text(row.get("quote_source"))
    memory_categories = _categories(passage)
    present_categories = _categories(message)
    lowered = _text(message).casefold()
    direct_invitation = any(signal in lowered for signal in _DIRECT_INVITATION)
    directly_on_topic = bool(memory_categories and memory_categories & present_categories)

    if memory_categories and not (direct_invitation or directly_on_topic):
        decision = "silent"
        surface_allowed = False
        reason = "The memory is high-intimacy and the present turn did not directly invite that topic."
        mode = "protective_silence"
    else:
        decision = "surface"
        surface_allowed = True
        reason = "The memory is either not high-intimacy or the present turn directly invited the same topic."
        mode = "proportionate_surface"

    return {
        "engine": "memory_privacy_guard",
        "version": MEMORY_PRIVACY_VERSION,
        "active": True,
        "decision": decision,
        "surface_allowed": surface_allowed,
        "source": source if surface_allowed else None,
        "mode": mode,
        "memory_categories": sorted(memory_categories),
        "present_categories": sorted(present_categories),
        "direct_invitation": direct_invitation,
        "directly_on_topic": directly_on_topic,
        "reason": reason,
        "instruction": (
            "Treat intimacy as a separate publication boundary. Do not surface highly private memory merely because "
            "it is relevant, current or useful. If Doug has not directly invited that topic, keep the memory silent. "
            "When the topic is explicitly invited, use the minimum detail needed for the present purpose. Never "
            "announce hidden retrieval or reveal unrelated intimate details."
        ),
        "governance": {
            "can_upgrade_prior_permission": False,
            "intimacy_is_separate_from_relevance": True,
            "minimum_necessary_disclosure": True,
            "uninvited_high_intimacy_surface_blocked": True,
            "silent_context_allowed": True,
            "unrelated_private_detail_prohibited": True,
            "being_known_not_watched": True,
        },
    }


__all__ = ["MEMORY_PRIVACY_VERSION", "build_memory_privacy_packet"]
