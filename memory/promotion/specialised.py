"""Create high-confidence episodic memories and identity anchors.

The ordinary promotion gate decides whether a raw row belongs in long-term
memory.  This module makes the narrower decisions required by Project L's
specialised autobiographical layers.  It is deliberately deterministic and
only accepts Doug-authored rows that already passed the canonical gate.
"""

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from memory.promotion.gate import evaluate_promotion


BRISBANE = ZoneInfo("Australia/Brisbane")
MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
MONTH_PATTERN = "|".join(MONTHS)

EVENT_SIGNALS = re.compile(
    r"\b(?:accepted|accident|achieved|appointment|began|birthday|born|"
    r"braces|clean|completed|died|ended|finished|first|flew|graduated|"
    r"launched|live|married|meeting|milestone|moved|paid|retired|session|"
    r"sober|started|stopped|travelled|trip|visited|won)\b",
    re.IGNORECASE,
)

IDENTITY_PATTERNS = (
    ("learning_style", re.compile(r"\bmy (?:preferred )?learning style\b|\bi learn best\b", re.I)),
    ("preference", re.compile(r"\bmy preference is\b|\bi prefer\b", re.I)),
    ("core_value", re.compile(r"\bmy (?:core )?values? (?:are|is)\b|\bi value\b", re.I)),
    ("purpose", re.compile(r"\bmy purpose is\b|\bi find purpose\b", re.I)),
    ("belief", re.compile(r"\bmy (?:core )?belief is\b|\bi believe\b", re.I)),
    ("principle", re.compile(r"\bmy principle is\b|\ba principle i live by\b", re.I)),
    ("support_need", re.compile(r"\bi (?:need|work best) (?:when|with)\b", re.I)),
    (
        "identity",
        re.compile(
            r"\bthis is who i am\b|\bmy identity\b|"
            r"\bi am (?:a|an) (?:father|dad|parent|veteran|builder|creator|"
            r"recovering alcoholic|person in recovery)\b",
            re.I,
        ),
    ),
)


def _text(value):
    return str(value or "").strip()


def _source_datetime(value):
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(BRISBANE)


def _valid_date(year, month, day):
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return ""


def extract_event_date(content, created_at=None):
    """Return ``(ISO date, basis, confidence)`` or an empty decision."""
    text = _text(content)

    match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
    if match:
        event_date = _valid_date(int(match[1]), int(match[2]), int(match[3]))
        if event_date:
            return event_date, "explicit_iso", 1.0

    match = re.search(
        rf"\b(\d{{1,2}})\s+({MONTH_PATTERN})\s+(20\d{{2}})\b",
        text,
        re.IGNORECASE,
    )
    if match:
        event_date = _valid_date(int(match[3]), MONTHS[match[2].lower()], int(match[1]))
        if event_date:
            return event_date, "explicit_date", 1.0

    match = re.search(
        rf"\b({MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?[,]?\s+(20\d{{2}})\b",
        text,
        re.IGNORECASE,
    )
    if match:
        event_date = _valid_date(int(match[3]), MONTHS[match[1].lower()], int(match[2]))
        if event_date:
            return event_date, "explicit_date", 1.0

    match = re.search(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b", text)
    if match:
        event_date = _valid_date(int(match[3]), int(match[2]), int(match[1]))
        if event_date:
            return event_date, "explicit_au_date", 1.0

    source_time = _source_datetime(created_at)
    if not source_time:
        return "", "", 0.0

    lowered = text.lower()
    if re.search(r"\b(?:today|this morning|this afternoon|this evening|tonight)\b", lowered):
        return source_time.date().isoformat(), "relative_to_created_at", 0.9
    if re.search(r"\b(?:yesterday|last night)\b", lowered):
        return (source_time.date() - timedelta(days=1)).isoformat(), "relative_to_created_at", 0.85

    return "", "", 0.0


def _summary(content, limit=900):
    lines = [_text(line) for line in _text(content).splitlines() if _text(line)]
    if not lines:
        return ""
    selected = []
    for line in lines:
        candidate = " — ".join(selected + [line])
        if len(candidate) > limit:
            break
        selected.append(line)
        if len(selected) >= 4:
            break
    return (" — ".join(selected) or lines[0])[:limit]


def build_episodic_payload(row, category="general"):
    promotion = evaluate_promotion(row)
    if not promotion["promote"]:
        return None

    content = _text(row.get("content"))
    event_date, basis, confidence = extract_event_date(content, row.get("created_at"))
    if not event_date or not EVENT_SIGNALS.search(content):
        return None

    return {
        "event_date": event_date,
        "category": _text(category) or "general",
        "summary": _summary(content),
        "confidence": confidence,
        "source_reference": row.get("id"),
        "memory_status": "ACTIVE",
        "metadata": {
            "source_table": "raw_catchall",
            "source_role": "user",
            "date_basis": basis,
            "pipeline": "specialised_promotion_v1",
        },
    }


def classify_identity_anchor(row):
    promotion = evaluate_promotion(row)
    if not promotion["promote"]:
        return ""

    content = _text(row.get("content"))
    # Identity anchors must be concise first-person truths, not whole reports
    # that happen to contain an identity phrase somewhere in the body.
    if len(content) > 800:
        return ""

    lowered = content.lower().lstrip()
    if re.match(
        r"^(?:hey\s+)?l[,\s:]+(?:what|who|how|do|does|did|is|are|can|could|would|should)\b",
        lowered,
    ):
        return ""
    if re.search(r"\bi am l\b|\bl(?:'s|’s) identity\b", lowered):
        return ""

    for anchor_type, pattern in IDENTITY_PATTERNS:
        if pattern.search(content):
            return anchor_type
    return ""


def build_identity_anchor_payload(row):
    anchor_type = classify_identity_anchor(row)
    if not anchor_type:
        return None

    promotion = evaluate_promotion(row)
    raw_id = row.get("id")
    return {
        "key": f"{anchor_type}:raw_{raw_id}",
        "value": _summary(row.get("content"), limit=700),
        "confidence": 1.0 if promotion["explicit"] else 0.95,
        "source_reference": raw_id,
        "memory_status": "ACTIVE",
    }


def _already_stored(client, table_name, raw_id):
    response = (
        client.table(table_name)
        .select("id")
        .eq("source_reference", raw_id)
        .limit(1)
        .execute()
    )
    return bool(response.data)


def _store_candidate(client, table_name, payload):
    if not payload:
        return "not_applicable"
    raw_id = payload.get("source_reference")
    if raw_id is None or _already_stored(client, table_name, raw_id):
        return "already_exists"
    client.table(table_name).insert(payload).execute()
    return "stored"


def write_specialised_memories(client, row, category="general"):
    """Idempotently write specialised records for one promoted raw row."""
    results = {}
    candidates = {
        "episodic": ("episodic_memories", build_episodic_payload(row, category)),
        "identity_anchor": ("identity_anchors", build_identity_anchor_payload(row)),
    }
    for name, (table_name, payload) in candidates.items():
        try:
            results[name] = _store_candidate(client, table_name, payload)
        except Exception as exc:
            results[name] = f"error:{type(exc).__name__}"
    return results
