"""Project L Layer 17: memory applicability and context-transfer guard.

A past lesson may be true in its original setting without transferring cleanly to
the present one. This layer checks whether a surfaceable associative memory is
sufficiently similar in domain/context before L uses it as present guidance.
Earlier gates remain ceilings: applicability can preserve or downgrade permission,
never upgrade it.
"""

from __future__ import annotations

import re


MEMORY_APPLICABILITY_VERSION = "1.0"

_DOMAIN_TERMS = {
    "relationships": ("friend", "relationship", "partner", "daughter", "son", "family", "sponsor", "pauline"),
    "recovery": ("recovery", "sober", "sobriety", "meeting", "aa", "na", "step", "sponsor"),
    "health": ("health", "doctor", "physio", "pain", "medication", "sleep", "injury", "shoulder", "heart"),
    "fitness_sport": ("gym", "hockey", "training", "exercise", "fitness", "workout", "game"),
    "diving": ("dive", "diving", "wreck", "equalise", "equalize", "depth", "buddy", "padi"),
    "travel": ("travel", "flight", "hotel", "bali", "trip", "resort", "airport"),
    "money": ("money", "finance", "financial", "super", "tax", "debt", "claim", "insurance", "investment"),
    "projects": ("project", "app", "build", "deploy", "github", "railway", "supabase", "layer", "code"),
}
_TRANSFER_SIGNALS = (
    "same principle", "apply that", "does that apply", "use that here", "similar situation",
    "like before", "same thing", "what worked before", "lesson from", "can i use",
)
_CONTEXT_SHIFTS = (
    "different person", "different situation", "this time", "but now", "unlike before",
    "different context", "not the same", "new situation",
)


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _domains(value: str) -> set[str]:
    text = _text(value).casefold()
    found = set()
    for domain, terms in _DOMAIN_TERMS.items():
        if any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms):
            found.add(domain)
    return found


def _lookup_evidence(rhee_packet: dict | None, source: str) -> dict:
    for row in (rhee_packet or {}).get("evidence") or []:
        if isinstance(row, dict) and _text(row.get("source")) == source:
            return row
    return {}


def build_memory_applicability_packet(
    message: str,
    cue_packet: dict | None,
    counterexample_packet: dict | None,
    rhee_packet: dict | None,
) -> dict:
    """Check whether an already-surfaceable memory transfers to this context."""
    cue = cue_packet or {}
    counterexample = counterexample_packet or {}
    if not cue.get("active") or not counterexample.get("active"):
        return {
            "engine": "memory_applicability_guard",
            "version": MEMORY_APPLICABILITY_VERSION,
            "active": False,
            "decision": "not_required",
            "surface_allowed": False,
            "instruction": "Memory applicability review was not required.",
        }

    prior_decision = str(counterexample.get("decision") or "discard")
    if prior_decision != "surface" or not counterexample.get("surface_allowed"):
        return {
            "engine": "memory_applicability_guard",
            "version": MEMORY_APPLICABILITY_VERSION,
            "active": True,
            "decision": prior_decision if prior_decision in {"silent", "discard"} else "silent",
            "surface_allowed": False,
            "source": None,
            "reason": "Earlier gates did not authorise surfacing; applicability review cannot upgrade permission.",
            "governance": {"can_upgrade_prior_permission": False},
        }

    source = _text(counterexample.get("source"))
    row = _lookup_evidence(rhee_packet, source)
    passage = _text(row.get("quote_source"))
    present_domains = _domains(message)
    memory_domains = _domains(passage)
    shared_domains = sorted(present_domains & memory_domains)
    present_text = _text(message).casefold()
    transfer_requested = any(signal in present_text for signal in _TRANSFER_SIGNALS)
    explicit_context_shift = any(signal in present_text for signal in _CONTEXT_SHIFTS)

    if present_domains and memory_domains:
        domain_alignment = len(present_domains & memory_domains) / max(1, len(present_domains | memory_domains))
    elif not present_domains and not memory_domains:
        domain_alignment = 0.5
    else:
        domain_alignment = 0.0

    # Domain mismatch is a warning, not proof of non-transfer. An explicit transfer
    # cue allows the memory to be mentioned as an analogy, not as established fact.
    if explicit_context_shift and not shared_domains:
        decision = "silent"
        surface_allowed = False
        mode = "non_transferable"
        reason = "The present turn explicitly marks a changed context and the retrieved memory shares no clear domain."
    elif not shared_domains and present_domains and memory_domains and not transfer_requested:
        decision = "silent"
        surface_allowed = False
        mode = "uncertain_transfer"
        reason = "The memory comes from a materially different domain; relevance alone does not establish transfer."
    elif not shared_domains and present_domains and memory_domains and transfer_requested:
        decision = "surface"
        surface_allowed = True
        mode = "analogy_only"
        reason = "Doug explicitly invited transfer across contexts; the memory may be surfaced only as an analogy, not a rule."
    else:
        decision = "surface"
        surface_allowed = True
        mode = "context_aligned"
        reason = "The present and remembered situations share enough contextual domain for cautious transfer."

    return {
        "engine": "memory_applicability_guard",
        "version": MEMORY_APPLICABILITY_VERSION,
        "active": True,
        "decision": decision,
        "surface_allowed": surface_allowed,
        "source": source if surface_allowed else None,
        "mode": mode,
        "present_domains": sorted(present_domains),
        "memory_domains": sorted(memory_domains),
        "shared_domains": shared_domains,
        "domain_alignment": round(domain_alignment, 2),
        "transfer_requested": transfer_requested,
        "explicit_context_shift": explicit_context_shift,
        "reason": reason,
        "instruction": (
            "Do not assume a true past lesson automatically transfers to a new context. Preserve the original setting. "
            "If the domains materially differ, keep the memory silent unless Doug explicitly invites an analogy. "
            "When analogy is invited, describe it as a possible transferable lesson, not as proof that the same outcome "
            "will occur. Earlier relevance, contrast, value and counterexample gates remain authoritative ceilings."
        ),
        "governance": {
            "can_upgrade_prior_permission": False,
            "past_truth_does_not_imply_present_applicability": True,
            "cross_domain_transfer_requires_caution": True,
            "analogy_is_not_fact": True,
            "context_shift_blocks_automatic_transfer": True,
            "original_context_must_be_preserved": True,
        },
    }


__all__ = ["MEMORY_APPLICABILITY_VERSION", "build_memory_applicability_packet"]
