"""Mary 2: bounded longitudinal intelligence over traceable evidence."""

from __future__ import annotations

import re
from datetime import datetime, timezone


LONGITUDINAL_SIGNALS = (
    "again", "always", "before", "change", "changed", "growth", "history",
    "keep doing", "over time", "pattern", "progress", "repeated", "trend",
    "last six months", "past six months", "last 6 months", "past 6 months",
    "report for pauline",
)

LIFECYCLE_STATES = (
    "Candidate", "Emerging", "Developing", "Established",
    "Weakening", "Historical", "Superseded",
)

CONTRADICTION_SIGNALS = (
    "contradict", "no longer", "not anymore", "stopped", "has stopped",
    "doesn't happen", "does not happen", "changed away", "opposite",
    "instead now", "used to, but", "used to but",
)

SUPERSESSION_SIGNALS = (
    "superseded", "replaced by", "no longer reflects", "old version of me",
    "historical version of me", "that was then", "not who i am now",
)

HEADER_PATTERN = re.compile(
    r"^(?P<score>\d+(?:\.\d+)?)\s*\|\s*"
    r"(?P<table>(?:(?:memory_|local_)[^|\s]+|episodic_memories|identity_anchors))"
    r"\s*\|\s*(?P<rest>.*)$",
    re.I,
)
DATE_PATTERN = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


def needs_longitudinal_context(message: str) -> bool:
    text = str(message or "").lower()
    return any(signal in text for signal in LONGITUDINAL_SIGNALS)


def _parse_datetime(text: str) -> datetime | None:
    created_match = re.search(r"CREATED_AT=([^|]+)", str(text or ""), re.I)
    candidates = [created_match.group(1).strip()] if created_match else []
    date_match = DATE_PATTERN.search(str(text or ""))
    if date_match:
        candidates.append(date_match.group(1))
    for value in candidates:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            continue
    return None


def _evidence_blocks(context: str) -> list[dict]:
    blocks = []
    current = None
    for raw_line in str(context or "").splitlines():
        clean = raw_line.strip()
        if not clean:
            continue
        if clean.startswith(("GOVERNED CAPABILITY RESULT", "CAPABILITY:", "STATUS:", "RESULT:")):
            if current:
                blocks.append(current)
                current = None
            if clean.startswith("RESULT:"):
                clean = clean.removeprefix("RESULT:").strip()
        match = HEADER_PATTERN.match(clean)
        if match:
            if current:
                blocks.append(current)
            rest = match.group("rest")
            memory_id = re.search(r"\bID=([^|\s]+)", rest, re.I)
            source_role = re.search(r"\bSOURCE_ROLE=([^|\s]+)", rest, re.I)
            current = {
                "ref": clean[:500],
                "score": float(match.group("score")),
                "table": match.group("table"),
                "id": memory_id.group(1) if memory_id else "",
                "source_role": source_role.group(1).upper() if source_role else "UNKNOWN",
                "header_date": _parse_datetime(rest),
                "content": [],
            }
            continue
        external_urls = re.findall(r"https?://[^\s)\]]+", clean)
        if external_urls and current is None:
            for url in external_urls:
                blocks.append({
                    "ref": f"external:{url[:450]}",
                    "score": 60.0,
                    "table": "external_source",
                    "id": "",
                    "source_role": "EXTERNAL",
                    "header_date": _parse_datetime(clean),
                    "content": [clean],
                })
            continue
        if (
            current is None
            and "independent sources" in clean.lower()
            and "confidence" in clean.lower()
        ):
            blocks.append({
                "ref": clean[:500],
                "score": 60.0,
                "table": "external_source",
                "id": "",
                "source_role": "EXTERNAL",
                "header_date": _parse_datetime(clean),
                "content": [clean],
            })
            continue
        if current and not clean.startswith((
            "RHEE ", "QUERY:", "MEMORIES FOUND:", "PROVENANCE:", "CONFLICT RULE:",
        )):
            current["content"].append(clean)
    if current:
        blocks.append(current)
    return blocks


def _episode(block: dict) -> dict:
    summary = " ".join(block.get("content") or []).strip()
    if not summary:
        rest = str(block.get("ref") or "").split("|", 2)
        summary = rest[-1].strip() if rest else ""
    event_date = _parse_datetime(summary) or block.get("header_date")
    lowered = summary.lower()
    direction = (
        "contradicts"
        if any(signal in lowered for signal in CONTRADICTION_SIGNALS)
        else "supports"
    )
    return {
        "evidence_ref": str(block.get("ref") or "")[:500],
        "table": str(block.get("table") or "")[:100],
        "id": str(block.get("id") or "")[:80],
        "event_date": event_date.date().isoformat() if event_date else None,
        "retrieval_score": max(0.0, min(100.0, float(block.get("score") or 0.0))),
        "source_role": str(block.get("source_role") or "UNKNOWN")[:40],
        "summary": summary[:700],
        "direction": direction,
    }


def _confidence_trajectory(episodes: list[dict]) -> list[dict]:
    ordered = sorted(
        episodes,
        key=lambda item: (item.get("event_date") is None, item.get("event_date") or ""),
    )
    confidence = 0.2
    trajectory = []
    for episode in ordered:
        evidence_weight = 0.18 if episode["source_role"] == "USER" else 0.1
        if episode["direction"] == "supports":
            confidence = min(0.92, confidence + evidence_weight)
        else:
            confidence = max(0.08, confidence - max(0.14, evidence_weight))
        trajectory.append({
            "event_date": episode.get("event_date"),
            "evidence_ref": episode.get("evidence_ref"),
            "direction": episode["direction"],
            "confidence": round(confidence, 2),
        })
    return trajectory


def _current_relevance(episodes: list[dict], now: datetime) -> str:
    text = " ".join(item.get("summary") or "" for item in episodes).lower()
    if any(signal in text for signal in SUPERSESSION_SIGNALS):
        return "superseded"
    dates = [
        datetime.fromisoformat(item["event_date"]).replace(tzinfo=timezone.utc)
        for item in episodes
        if item.get("event_date")
    ]
    if not dates:
        return "undated"
    ages = [(now - value).days for value in dates]
    if min(ages) > 365:
        return "historical"
    if max(ages) > 365:
        return "mixed"
    return "current"


def _lifecycle_state(
    supporting: list[dict],
    contradicting: list[dict],
    relevance: str,
) -> str:
    if relevance == "superseded":
        return "Superseded"
    if relevance == "historical":
        return "Historical"
    if len(contradicting) >= 2 and len(contradicting) * 2 >= max(1, len(supporting)):
        return "Weakening"
    if len(supporting) >= 4:
        return "Established"
    if len(supporting) == 3:
        return "Developing"
    if len(supporting) == 2:
        return "Emerging"
    return "Candidate"


def build_longitudinal_packet(
    message: str,
    evidence_context: str,
    now: datetime | None = None,
) -> dict:
    active = needs_longitudinal_context(message)
    reference_time = now or datetime.now(timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)

    episodes = [
        _episode(block) for block in _evidence_blocks(evidence_context)
    ] if active else []
    supporting = [item for item in episodes if item["direction"] == "supports"]
    contradicting = [item for item in episodes if item["direction"] == "contradicts"]
    relevance = _current_relevance(episodes, reference_time) if active else "not_applicable"
    state = _lifecycle_state(supporting, contradicting, relevance) if active else "Candidate"
    dated = [item["event_date"] for item in episodes if item.get("event_date")]
    trajectory = _confidence_trajectory(episodes)
    pattern_threshold_met = (
        len(supporting) >= 2
        and state not in {"Candidate", "Weakening", "Historical", "Superseded"}
    )

    return {
        "engine": "mary",
        "version": "5.0",
        "active": active,
        "pattern_query": str(message or "")[:1200] if active else "",
        "lifecycle_state": state,
        "first_seen": min(dated) if dated else None,
        "last_seen": max(dated) if dated else None,
        "supporting_episodes": supporting[:12],
        "contradicting_episodes": contradicting[:12],
        "confidence_trajectory": trajectory[:24],
        "current_relevance": relevance,
        "current_identity_precedence": True,
        "historical_evidence_use": (
            "context_only"
            if relevance in {"historical", "superseded"}
            else "eligible_only_when_consistent_with_current_evidence"
        ),
        "evidence_refs": [item["evidence_ref"] for item in episodes[:12]],
        "pattern_threshold_met": pattern_threshold_met,
        "instruction": (
            "Compare supporting and contradicting episodes across time. Apply the lifecycle "
            "state and confidence trajectory. Current evidence and explicit current identity "
            "outrank historical patterns."
            if active else
            "Longitudinal interpretation was not required for this request."
        ),
        "caution": (
            "Evidence does not support a current established pattern; present the lifecycle "
            "state and limitations without collapsing Doug today into historical Doug."
            if active and not pattern_threshold_met else ""
        ),
    }
