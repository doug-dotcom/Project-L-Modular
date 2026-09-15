"""Project L Layer 4: governed decision memory.

Captures only explicit user-authored decisions and only the rationale or rejected
alternatives Doug actually states. Missing reasons remain missing; the layer never
reverse-engineers motives from later outcomes or model inference.
"""

from __future__ import annotations

import re


DECISION_MEMORY_VERSION = "1.0"

DECISION_PATTERNS = (
    r"\bi decided\s+(?P<decision>.+)",
    r"\bwe decided\s+(?P<decision>.+)",
    r"\bi(?:'m| am) going with\s+(?P<decision>.+)",
    r"\bi chose\s+(?P<decision>.+)",
    r"\bi choose\s+(?P<decision>.+)",
    r"\bwe(?:'re| are) going with\s+(?P<decision>.+)",
    r"\bgo with\s+(?P<decision>.+)",
    r"\bnumber\s+(?P<decision>\d+(?:\s+it is)?)\b",
)

RATIONALE_PATTERNS = (
    r"\bbecause\s+(?P<reason>.+?)(?=(?:\s+(?:instead of|rather than|over)\s+)|[.!?]|$)",
    r"\bdue to\s+(?P<reason>.+?)(?=(?:\s+(?:instead of|rather than|over)\s+)|[.!?]|$)",
)

REJECTED_PATTERNS = (
    r"\binstead of\s+(?P<alternative>.+?)(?=[.!?]|$)",
    r"\brather than\s+(?P<alternative>.+?)(?=[.!?]|$)",
    r"\bover\s+(?P<alternative>.+?)(?=[.!?]|$)",
)


def _clean(value: object, limit: int = 1200) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" .,-—")[:limit]


def decision_recall_requested(message: str) -> bool:
    text = _clean(message).casefold()
    return any(phrase in text for phrase in (
        "why did i decide", "why did we decide", "why did i choose",
        "why did we choose", "what did i decide", "what did we decide",
        "what did i choose", "what did we choose", "what decision did",
        "what decisions did", "what did i reject", "what did we reject",
        "which option did i choose", "which option did we choose",
        "decision rationale", "reason i chose", "reason we chose",
    ))


def extract_decision_memory(message: str) -> dict | None:
    """Extract an explicit decision without inventing missing rationale."""
    text = _clean(message, 4000)
    if not text or text.endswith("?"):
        return None

    decision_match = None
    for pattern in DECISION_PATTERNS:
        decision_match = re.search(pattern, text, re.IGNORECASE)
        if decision_match:
            break
    if not decision_match:
        return None

    raw_decision = _clean(decision_match.group("decision"))
    # Stop the decision phrase before explicit rationale/alternative markers.
    decision = re.split(
        r"\s+(?:because|due to|instead of|rather than|over)\s+",
        raw_decision,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    decision = _clean(decision)
    if not decision:
        return None

    rationale = ""
    for pattern in RATIONALE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            rationale = _clean(match.group("reason"))
            break

    rejected = []
    for pattern in REJECTED_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            alternative = _clean(match.group("alternative"))
            if alternative and alternative.casefold() not in {item.casefold() for item in rejected}:
                rejected.append(alternative)

    return {
        "engine": "decision_memory",
        "version": DECISION_MEMORY_VERSION,
        "decision": decision,
        "rationale": rationale or None,
        "rejected_alternatives": rejected[:5],
        "source_text": text,
        "rationale_status": "explicit" if rationale else "not_stated",
        "alternative_status": "explicit" if rejected else "not_stated",
        "governance": {
            "user_authored_only": True,
            "infer_missing_rationale": False,
            "infer_rejected_alternatives": False,
            "later_outcomes_do_not_rewrite_original_reason": True,
        },
    }


def canonical_decision_text(record: dict | None) -> str:
    if not record:
        return ""
    parts = [f"DECISION MEMORY — Decision: {record['decision']}"]
    parts.append(
        f"Rationale stated at the time: {record['rationale']}"
        if record.get("rationale") else
        "Rationale stated at the time: not recorded"
    )
    alternatives = record.get("rejected_alternatives") or []
    parts.append(
        "Rejected alternatives stated at the time: " + "; ".join(alternatives)
        if alternatives else
        "Rejected alternatives stated at the time: not recorded"
    )
    return " | ".join(parts)


__all__ = [
    "DECISION_MEMORY_VERSION",
    "canonical_decision_text",
    "decision_recall_requested",
    "extract_decision_memory",
]
