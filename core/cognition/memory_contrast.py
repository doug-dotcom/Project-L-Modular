"""Project L Layer 13: memory contrast and false-association guard.

Cue-driven retrieval can return several plausible memories. This layer checks
whether the best-looking memory is actually distinctive enough to use. It does
not create facts or rank truth; it prevents near-neighbour memories from being
collapsed into one story merely because they share vocabulary or emotional tone.
"""

from __future__ import annotations

import re


MEMORY_CONTRAST_VERSION = "1.0"
MAX_CANDIDATES = 6
AMBIGUITY_MARGIN = 0.08

_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has",
    "had", "was", "were", "are", "is", "you", "your", "me", "my", "i",
    "it", "to", "of", "in", "on", "at", "a", "an", "as", "but", "or",
    "feel", "feeling", "felt", "again", "before", "same", "thing",
}


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _terms(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9']+", _text(value).casefold())
        if len(token) >= 3 and token not in _STOP
    }


def _entities(value: str) -> set[str]:
    text = _text(value)
    found = set(re.findall(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*\b", text))
    return {item for item in found if item not in {"The", "This", "That", "Doug"}}


def _dates(value: str) -> set[str]:
    text = _text(value)
    matches = re.findall(
        r"\b(?:20\d{2}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/20\d{2}|"
        r"\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)\s+20\d{2})\b",
        text,
        re.I,
    )
    return {item.casefold() for item in matches}


def _overlap(left: str, right: str) -> float:
    a, b = _terms(left), _terms(right)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, min(len(a), 8))


def _evidence_lookup(rhee_packet: dict) -> dict[str, dict]:
    result = {}
    for row in (rhee_packet or {}).get("evidence") or []:
        if not isinstance(row, dict):
            continue
        source = _text(row.get("source"))
        if source and source not in result:
            result[source] = row
    return result


def build_memory_contrast_packet(
    message: str,
    cue_packet: dict | None,
    relevance_packet: dict | None,
    rhee_packet: dict | None,
) -> dict:
    """Check whether associative candidates are sufficiently distinct to use.

    A close race between different people, dates or events means ambiguity. In
    that case L may keep the context silently but must not surface one candidate
    as though it were clearly the remembered event.
    """
    cue = cue_packet or {}
    relevance = relevance_packet or {}
    if not cue.get("active") or not relevance.get("active"):
        return {
            "engine": "memory_contrast_guard",
            "version": MEMORY_CONTRAST_VERSION,
            "active": False,
            "decision": "not_required",
            "surface_allowed": False,
            "ambiguous": False,
            "candidates": [],
            "instruction": "Memory contrast was not required.",
        }

    lookup = _evidence_lookup(rhee_packet or {})
    ranked = sorted(
        [item for item in relevance.get("reviewed") or [] if item.get("disposition") != "discard"],
        key=lambda item: float(item.get("relevance") or 0.0),
        reverse=True,
    )[:MAX_CANDIDATES]

    candidates = []
    for item in ranked:
        source = _text(item.get("source"))
        row = lookup.get(source) or {}
        passage = _text(row.get("quote_source"))
        candidates.append({
            "source": source,
            "relevance": round(float(item.get("relevance") or 0.0), 2),
            "message_overlap": round(_overlap(message, passage), 2),
            "entities": sorted(_entities(passage)),
            "dates": sorted(_dates(passage)),
            "passage": passage[:700],
        })

    if not candidates:
        return {
            "engine": "memory_contrast_guard",
            "version": MEMORY_CONTRAST_VERSION,
            "active": True,
            "decision": "discard",
            "surface_allowed": False,
            "ambiguous": False,
            "candidates": [],
            "instruction": "No non-discarded associative memory survived relevance arbitration.",
        }

    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None
    message_entities = _entities(message)
    top_entity_match = bool(message_entities & set(top["entities"]))
    second_entity_match = bool(second and message_entities & set(second["entities"]))

    close_race = bool(
        second
        and abs(top["relevance"] - second["relevance"]) <= AMBIGUITY_MARGIN
        and second["message_overlap"] >= 0.18
    )
    distinct_people = bool(
        second and top["entities"] and second["entities"]
        and set(top["entities"]) != set(second["entities"])
    )
    distinct_dates = bool(
        second and top["dates"] and second["dates"]
        and set(top["dates"]) != set(second["dates"])
    )
    explicit_entity_resolves = top_entity_match and not second_entity_match
    ambiguous = bool(close_race and (distinct_people or distinct_dates) and not explicit_entity_resolves)

    relevance_surface = bool(relevance.get("decision") == "surface" and relevance.get("surface"))
    if ambiguous:
        decision = "silent"
        surface_allowed = False
        reason = "Competing memories are too close and contain distinguishing people or dates."
    elif relevance_surface:
        decision = "surface"
        surface_allowed = True
        reason = "The leading memory is sufficiently distinct from competing retrieved memories."
    else:
        decision = "silent" if relevance.get("decision") == "silent" else "discard"
        surface_allowed = False
        reason = "Relevance arbitration did not authorise surfacing."

    return {
        "engine": "memory_contrast_guard",
        "version": MEMORY_CONTRAST_VERSION,
        "active": True,
        "decision": decision,
        "surface_allowed": surface_allowed,
        "ambiguous": ambiguous,
        "reason": reason,
        "winner": top["source"] if surface_allowed else None,
        "candidates": candidates,
        "instruction": (
            "Treat this as the final contrast gate for cue-driven memory. Do not merge distinct "
            "events because they share themes, emotions or vocabulary. If ambiguous, use the memory "
            "only silently and avoid naming a specific past event unless Doug supplies a clarifying cue. "
            "If one candidate is clearly distinguished by the present person/date/event cue, it may "
            "surface only if the earlier relevance and confidence gates also allow it."
        ),
        "governance": {
            "near_match_is_not_same_event": True,
            "competing_memories_checked": True,
            "ambiguity_blocks_surface": True,
            "event_merging_prohibited": True,
            "surface_requires_prior_relevance_permission": True,
            "clarification_preferred_over_guessing": True,
        },
    }


__all__ = ["MEMORY_CONTRAST_VERSION", "build_memory_contrast_packet"]
