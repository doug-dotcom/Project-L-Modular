"""Project L Layer 6: personal timeline intelligence over retrieved evidence.

The timeline layer turns dated, governed evidence into a bounded chronology. It
never invents dates, treats recording time as event time, or upgrades importance
merely because an event is emotionally vivid. Turning points require explicit
change/milestone language or corroboration across dated evidence.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import calendar
import re


TIMELINE_VERSION = "1.0"
MAX_EVENTS = 40

TIMELINE_SIGNALS = (
    "timeline", "chronology", "turning point", "turning points", "story of my",
    "story of 2026", "year so far", "this year so far", "last six months",
    "last 6 months", "past six months", "past 6 months", "what changed around",
    "what changed in", "what happened around", "what happened in", "major changes",
    "biggest changes", "major moments", "key moments", "life story",
)

HEADER = re.compile(
    r"^(?P<score>\d+(?:\.\d+)?)\s*\|\s*(?P<table>[^|\s]+)\s*\|\s*(?P<rest>.*)$",
    re.I,
)
DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
TURNING_SIGNALS = (
    "started", "stopped", "ended", "began", "completed", "finished", "launched",
    "accepted", "approved", "moved", "changed", "breakthrough", "milestone",
    "first", "qualified", "graduated", "married", "separated", "died", "born",
    "sober", "clean", "won", "lost", "diagnosed", "retired",
)


def timeline_query_requested(message: str) -> bool:
    text = " ".join(str(message or "").lower().split())
    if any(signal in text for signal in TIMELINE_SIGNALS):
        return True
    return bool(re.search(r"\b(?:show|give|tell) me (?:my|the) .*(?:timeline|chronology)\b", text))


def _parse_date(text: str) -> str | None:
    match = DATE_RE.search(str(text or ""))
    return match.group(1) if match else None


def _domain(table: str) -> str:
    table = str(table or "").lower()
    if table.startswith("memory_"):
        return table.removeprefix("memory_")
    if table.startswith("short_term_"):
        return table.removeprefix("short_term_")
    if table == "episodic_memories":
        return "episodic"
    if table == "identity_anchors":
        return "identity"
    return table or "unknown"


def _events(context: str) -> list[dict]:
    result = []
    current = None
    for raw in str(context or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        match = HEADER.match(line)
        if match:
            if current:
                result.append(current)
            rest = match.group("rest")
            current = {
                "score": float(match.group("score")),
                "table": match.group("table"),
                "domain": _domain(match.group("table")),
                "header": line[:500],
                "date": _parse_date(rest),
                "content": [],
            }
            continue
        if current and not line.startswith(("RHEE ", "QUERY:", "PROVENANCE:", "MEMORIES FOUND:", "CONFLICT RULE:")):
            current["content"].append(line)
    if current:
        result.append(current)

    events = []
    seen = set()
    for item in result:
        summary = " ".join(item["content"]).strip()
        event_date = _parse_date(summary) or item.get("date")
        if not event_date:
            continue
        key = (event_date, summary[:250].casefold())
        if key in seen:
            continue
        seen.add(key)
        lowered = summary.lower()
        turning = any(signal in lowered for signal in TURNING_SIGNALS)
        events.append({
            "event_date": event_date,
            "domain": item["domain"],
            "summary": summary[:800],
            "retrieval_score": round(max(0.0, min(100.0, item["score"])), 2),
            "turning_point_candidate": turning,
            "evidence_ref": item["header"],
        })
    return sorted(events, key=lambda item: (item["event_date"], -item["retrieval_score"]))


def _month_number(name: str) -> int | None:
    lowered = name.lower()
    for month in range(1, 13):
        if lowered in {calendar.month_name[month].lower(), calendar.month_abbr[month].lower()}:
            return month
    return None


def _requested_window(message: str, today: date) -> tuple[str | None, str | None, str]:
    text = str(message or "").lower()
    year = re.search(r"\b(20\d{2})\b", text)
    month = re.search(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b",
        text,
    )
    if month:
        m = _month_number(month.group(1).replace("sept", "sep"))
        y = int(year.group(1)) if year else today.year
        start = date(y, m, 1)
        end = date(y + int(m == 12), (m % 12) + 1, 1)
        return start.isoformat(), end.isoformat(), "month"
    if "last six months" in text or "last 6 months" in text or "past six months" in text or "past 6 months" in text:
        month_index = today.year * 12 + today.month - 1 - 5
        y, zero = divmod(month_index, 12)
        start = date(y, zero + 1, 1)
        return start.isoformat(), (today + timedelta(days=1)).isoformat(), "six_months"
    if year:
        y = int(year.group(1))
        return date(y, 1, 1).isoformat(), date(y + 1, 1, 1).isoformat(), "year"
    if "this year" in text or "year so far" in text:
        return date(today.year, 1, 1).isoformat(), (today + timedelta(days=1)).isoformat(), "year_to_date"
    return None, None, "all_retrieved"


def build_personal_timeline_packet(message: str, evidence_context: str, *, today: date | None = None) -> dict:
    active = timeline_query_requested(message)
    reference = today or datetime.now(timezone.utc).date()
    if not active:
        return {
            "engine": "personal_timeline",
            "version": TIMELINE_VERSION,
            "active": False,
            "events": [],
            "turning_points": [],
            "status": "not_required",
        }

    start, end, mode = _requested_window(message, reference)
    events = _events(evidence_context)
    if start:
        events = [item for item in events if item["event_date"] >= start and (not end or item["event_date"] < end)]

    events = events[:MAX_EVENTS]
    turning = [item for item in events if item["turning_point_candidate"]]
    domains = sorted({item["domain"] for item in events if item["domain"] != "unknown"})

    return {
        "engine": "personal_timeline",
        "version": TIMELINE_VERSION,
        "active": True,
        "status": "complete" if events else "no_dated_evidence",
        "window": {"mode": mode, "from": start, "to_exclusive": end},
        "event_count": len(events),
        "domains": domains,
        "events": events,
        "turning_points": turning[:12],
        "instruction": (
            "Tell the chronology from dated evidence only. Group nearby events when useful, distinguish event date from recording date, "
            "and call something a turning point only when the supplied evidence shows a meaningful transition or milestone. "
            "If a period has little or no dated evidence, say so rather than filling the gap. Current evidence outranks stale historical labels."
        ),
        "governance": {
            "invent_dates": False,
            "recording_time_is_event_time": False,
            "gaps_are_unknown": True,
            "turning_points_require_evidence": True,
            "max_events": MAX_EVENTS,
        },
    }


__all__ = ["TIMELINE_VERSION", "timeline_query_requested", "build_personal_timeline_packet"]
