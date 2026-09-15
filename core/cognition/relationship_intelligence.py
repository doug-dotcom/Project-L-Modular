"""Project L Layer 5: governed relationship intelligence over retrieved evidence.

This layer builds an evolving, evidence-bounded view of an important person or
relationship. It never invents closeness, motives, feelings, conflict, or current
status. Historical relationship labels remain historical unless newer evidence
supports that they are still current.
"""

from __future__ import annotations

import re
from datetime import datetime


RELATIONSHIP_INTELLIGENCE_VERSION = "1.0"
DATE_PATTERN = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
HEADER_PATTERN = re.compile(
    r"^(?P<score>\d+(?:\.\d+)?)\s*\|\s*"
    r"(?P<table>(?:(?:memory_|short_term_|local_)[^|\s]+|episodic_memories|identity_anchors|raw_catchall))"
    r"\s*\|\s*(?P<rest>.*)$",
    re.I,
)

RELATIONSHIP_QUERY_PATTERNS = (
    re.compile(r"\bwho is\s+(?P<name>[A-Z][A-Za-z'’.-]*(?:\s+[A-Z][A-Za-z'’.-]*){0,3})\s+to me\b"),
    re.compile(r"\b(?:my )?relationship with\s+(?P<name>[A-Z][A-Za-z'’.-]*(?:\s+[A-Z][A-Za-z'’.-]*){0,3})\b"),
    re.compile(r"\bhow are things with\s+(?P<name>[A-Z][A-Za-z'’.-]*(?:\s+[A-Z][A-Za-z'’.-]*){0,3})\b"),
    re.compile(r"\bwhat(?:'s| is) been happening with\s+(?P<name>[A-Z][A-Za-z'’.-]*(?:\s+[A-Z][A-Za-z'’.-]*){0,3})\b", re.I),
    re.compile(r"\btell me about\s+(?P<name>[A-Z][A-Za-z'’.-]*(?:\s+[A-Z][A-Za-z'’.-]*){0,3})\b"),
)

RELATIONSHIP_ROLE_PATTERNS = (
    re.compile(r"\b(?P<name>[A-Z][A-Za-z'’.-]*(?:\s+[A-Z][A-Za-z'’.-]*){0,3})\s+is my\s+(?P<role>best friend|friend|daughter|son|child|brother|sister|half-brother|half brother|mother|mum|father|dad|wife|husband|partner|fianc(?:e|é|ée)|ex-wife|ex-husband|ex-partner|sponsor|psychologist)\b", re.I),
    re.compile(r"\bmy\s+(?P<role>best friend|friend|daughter|son|child|brother|sister|half-brother|half brother|mother|mum|father|dad|wife|husband|partner|fianc(?:e|é|ée)|ex-wife|ex-husband|ex-partner|sponsor|psychologist)\s+(?P<name>[A-Z][A-Za-z'’.-]*(?:\s+[A-Z][A-Za-z'’.-]*){0,3})\b", re.I),
)

STATUS_TERMS = {
    "ended": ("ended", "broke up", "separated", "relationship ended"),
    "deceased": ("died", "deceased", "passed away"),
    "engaged": ("engaged", "fiancé", "fiance", "fiancée", "fiancee"),
    "married": ("married", "wife", "husband"),
    "friendship": ("best friend", "friend"),
    "active_contact": ("spoke to", "talked to", "met with", "saw ", "called ", "messaged "),
}

UNRESOLVED_TERMS = (
    "still need", "need to", "follow up", "unresolved", "next time", "waiting for",
    "haven't", "have not", "yet to", "to discuss", "to ask",
)


def _clip(value: object, limit: int = 700) -> str:
    return " ".join(str(value or "").split())[:limit]


def relationship_query_requested(message: str) -> bool:
    text = str(message or "")
    lowered = text.casefold()
    if any(pattern.search(text) for pattern in RELATIONSHIP_QUERY_PATTERNS):
        return True
    return any(signal in lowered for signal in (
        "relationship with", "how are things with", "important people in my life",
        "what has happened with", "what's happened with", "whats happened with",
        "relationship history", "relationship timeline",
    ))


def extract_relationship_subject(message: str) -> str:
    text = str(message or "")
    for pattern in RELATIONSHIP_QUERY_PATTERNS:
        match = pattern.search(text)
        if match:
            return _clip(match.group("name"), 120)
    return ""


def _event_date(text: str) -> str | None:
    match = DATE_PATTERN.search(str(text or ""))
    return match.group(1) if match else None


def _blocks(context: str) -> list[dict]:
    blocks: list[dict] = []
    current: dict | None = None
    for raw in str(context or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        match = HEADER_PATTERN.match(line)
        if match:
            if current:
                blocks.append(current)
            current = {
                "table": match.group("table"),
                "score": float(match.group("score")),
                "header": line[:500],
                "date": _event_date(match.group("rest")),
                "content": [],
            }
            continue
        if current and not line.startswith(("RHEE ", "QUERY:", "MEMORIES FOUND:", "PROVENANCE:", "CONFLICT RULE:")):
            current["content"].append(line)
    if current:
        blocks.append(current)
    return blocks


def _explicit_roles(subject: str, text: str) -> list[dict]:
    roles = []
    for pattern in RELATIONSHIP_ROLE_PATTERNS:
        for match in pattern.finditer(text):
            name = _clip(match.group("name"), 120)
            if subject and subject.casefold() not in name.casefold() and name.casefold() not in subject.casefold():
                continue
            roles.append({
                "person": name,
                "role": _clip(match.group("role"), 80).lower(),
                "basis": "explicit_user-authored_relationship_label",
            })
    unique = []
    seen = set()
    for item in roles:
        key = (item["person"].casefold(), item["role"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:8]


def _status_markers(text: str) -> list[str]:
    lower = text.casefold()
    found = []
    for status, terms in STATUS_TERMS.items():
        if any(term in lower for term in terms):
            found.append(status)
    return found


def build_relationship_packet(message: str, evidence_context: str) -> dict:
    requested = relationship_query_requested(message)
    subject = extract_relationship_subject(message)
    if not requested:
        return {
            "engine": "relationship_intelligence",
            "version": RELATIONSHIP_INTELLIGENCE_VERSION,
            "active": False,
            "subject": "",
            "instruction": "Relationship intelligence was not required for this turn.",
        }

    blocks = _blocks(evidence_context)
    relevant = []
    for block in blocks:
        summary = _clip(" ".join(block.get("content") or []))
        table = str(block.get("table") or "")
        subject_match = bool(subject and subject.casefold() in summary.casefold())
        relationship_table = table in {"memory_relationships", "short_term_relationships"}
        family_table = table in {"memory_family", "short_term_family"}
        if subject_match or (not subject and (relationship_table or family_table)):
            relevant.append({
                "table": table,
                "score": block.get("score"),
                "event_date": _event_date(summary) or block.get("date"),
                "summary": summary,
                "status_markers": _status_markers(summary),
                "source_ref": block.get("header"),
            })

    relevant.sort(key=lambda item: (item.get("event_date") is None, item.get("event_date") or ""))
    combined = " ".join(item["summary"] for item in relevant)
    roles = _explicit_roles(subject, combined)
    dates = [
        {"date": item["event_date"], "summary": item["summary"][:350], "source_ref": item["source_ref"]}
        for item in relevant if item.get("event_date")
    ]
    unresolved = [
        {"summary": item["summary"][:400], "source_ref": item["source_ref"]}
        for item in relevant
        if any(term in item["summary"].casefold() for term in UNRESOLVED_TERMS)
    ]
    recent = list(reversed(relevant[-6:]))
    latest_status = []
    for item in recent:
        for marker in item.get("status_markers") or []:
            if marker not in latest_status:
                latest_status.append(marker)

    return {
        "engine": "relationship_intelligence",
        "version": RELATIONSHIP_INTELLIGENCE_VERSION,
        "active": True,
        "subject": subject,
        "evidence_count": len(relevant),
        "explicit_relationship_labels": roles,
        "latest_status_markers": latest_status[:6],
        "significant_dates": dates[-10:],
        "recent_events": recent,
        "unresolved_threads": unresolved[-6:],
        "current_status_verified": False,
        "instruction": (
            "Use this as an evolving relationship view, not a static profile. Prefer recent dated evidence over old labels. "
            "State relationship roles only when explicitly supported. Historical labels remain historical unless current evidence confirms them. "
            "Never infer the other person's motives, feelings, intentions, diagnosis, or private state. Distinguish Doug's perspective from verified events. "
            "If current status is not directly established, say what is known without upgrading it to a current fact."
        ),
        "governance": {
            "motives_may_be_inferred": False,
            "feelings_may_be_inferred": False,
            "historical_label_is_current_by_default": False,
            "doug_perspective_is_other_person_fact": False,
            "current_status_requires_recent_direct_evidence": True,
        },
    }


__all__ = [
    "RELATIONSHIP_INTELLIGENCE_VERSION",
    "build_relationship_packet",
    "extract_relationship_subject",
    "relationship_query_requested",
]
