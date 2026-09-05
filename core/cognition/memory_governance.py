"""Pure Carol, Sara and Mary stages for durable-memory formation."""

from __future__ import annotations

import re
from datetime import datetime, timezone


VALUE_SIGNALS = {
    "family": "Family",
    "truth": "Truth",
    "recovery": "Recovery",
    "service": "Service",
    "love": "Love",
    "safe": "Safety",
    "agency": "Agency",
    "project l": "Project L",
}

DOMAIN_SIGNALS = {
    "memory_project_l": ("project l", "rike", "rhee", "carol", "sara", "mary", "quinn"),
    "memory_family": ("iyla", "ashton", "luella", "mehlia", "children", "family"),
    "memory_relationships": ("leah", "tamara", "cass", "relationship"),
    "memory_recovery": ("recovery", "sobriety", "sober", "aa", "na", "pauline"),
    "memory_health": ("health", "sleep", "weight", "doctor", "medication"),
    "memory_sport": ("hockey", "sport", "gym", "training"),
    "memory_work": ("work", "business", "client"),
}

PATTERN_SIGNALS = ("again", "always", "pattern", "realised", "learned", "growth", "used to")


def _text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _has_signal(text: str, signal: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(signal)}(?!\w)", text, re.I))


def carol_normalise(row: dict) -> dict:
    content = _text((row or {}).get("content"))
    lowered = content.lower()
    scores = {
        table: sum(_has_signal(lowered, signal) for signal in signals)
        for table, signals in DOMAIN_SIGNALS.items()
    }
    target = max(scores, key=scores.get) if any(scores.values()) else "memory_general"

    subjects = []
    for signals in DOMAIN_SIGNALS.values():
        for signal in signals:
            if _has_signal(lowered, signal) and signal not in subjects:
                subjects.append(signal.title())

    values = [value for signal, value in VALUE_SIGNALS.items() if _has_signal(lowered, signal)]
    return {
        "stage": "carol_v5",
        "content": content,
        "target_table": target,
        "subjects": subjects,
        "values": list(dict.fromkeys(values)),
        "source": {
            "table": "raw_catchall",
            "id": (row or {}).get("id"),
            "role": _text((row or {}).get("role")).lower(),
            "created_at": (row or {}).get("created_at"),
        },
    }


def sara_govern(carol_packet: dict, promotion: dict) -> dict:
    content = carol_packet.get("content", "")
    lowered = content.lower()
    explicit = bool(promotion.get("explicit"))
    evidence_quality = 100 if carol_packet.get("source", {}).get("role") == "user" else 0
    importance = 50 + (25 if explicit else 0)
    importance += 10 if carol_packet.get("values") else 0
    salience = 45 + min(25, len(carol_packet.get("subjects", [])) * 5)
    salience += 15 if any(word in lowered for word in ("important", "milestone", "breakthrough")) else 0
    importance = min(100, importance)
    salience = min(100, salience)
    return {
        "stage": "sara_v2",
        "approved": bool(promotion.get("promote")) and evidence_quality == 100,
        "reason": promotion.get("reason", "unknown"),
        "importance": importance,
        "salience": salience,
        "anchor": explicit and (importance >= 75 or salience >= 75),
        "evidence_quality": evidence_quality,
    }


def mary_integrate(carol_packet: dict, sara_packet: dict) -> dict:
    content = carol_packet.get("content", "")
    lowered = content.lower()
    signals = [signal for signal in PATTERN_SIGNALS if _has_signal(lowered, signal)]
    source = carol_packet.get("source") or {}
    observed_at = source.get("created_at")
    return {
        "stage": "mary_v5",
        "applied": bool(signals),
        "pattern_signals": signals,
        "lifecycle_state": "Candidate",
        "first_seen": observed_at,
        "last_seen": observed_at,
        "supporting_episodes": [{
            "source_table": source.get("table"),
            "source_id": source.get("id"),
            "observed_at": observed_at,
        }] if signals else [],
        "contradicting_episodes": [],
        "confidence_trajectory": [{
            "observed_at": observed_at,
            "direction": "supports",
            "confidence": 0.2,
        }] if signals else [],
        "current_relevance": "current",
        "current_identity_precedence": True,
        "instruction": (
            "Treat this as a Candidate until independent episodes corroborate it. "
            "Current identity and current evidence outrank historical patterns."
        ),
    }


def build_memory_payload(row: dict, promotion: dict) -> tuple[dict, dict]:
    carol = carol_normalise(row)
    sara = sara_govern(carol, promotion)
    mary = mary_integrate(carol, sara)
    processed = [carol["stage"], sara["stage"]]
    if mary["applied"]:
        processed.append(mary["stage"])

    payload = {
        "raw_id": carol["source"]["id"],
        "content": carol["content"],
        "primary_subject": carol["subjects"][0] if carol["subjects"] else None,
        "subjects": carol["subjects"],
        "importance": sara["importance"],
        "salience": sara["salience"],
        "anchor": sara["anchor"],
        "values": carol["values"],
        "preferences": [],
        "relationships": [],
        "metadata": {
            "source_table": "raw_catchall",
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "pipeline": "governed_memory_v3",
            "promotion_gate": dict(promotion),
            "provenance": carol["source"],
            "mary": mary,
        },
        "processed_by": processed,
    }
    audit = {"carol": carol, "sara": sara, "mary": mary}
    return payload, audit
