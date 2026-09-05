"""Persist Allegra growth candidates without mistaking repetition for proof."""

from __future__ import annotations

import hashlib
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

IGNORED_LESSONS = {
    "a meaningful pattern has been detected and requires further exploration",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _get_supabase():
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_KEY", "")
    return create_client(url, key) if url and key else None


def normalise_lesson(lesson):
    text = re.sub(r"\s+", " ", str(lesson or "").strip().lower())
    return re.sub(r"[^a-z0-9\s]", "", text).strip()


def lesson_fingerprint(lesson):
    normalised = normalise_lesson(lesson)
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest() if normalised else ""


def calculate_trend(occurrences):
    if occurrences <= 1:
        return "emerging"
    if occurrences <= 3:
        return "strengthening"
    if occurrences <= 9:
        return "established"
    return "deeply_reinforced"


def calculate_confidence(occurrences, validated_occurrences=0, contradiction_count=0):
    """Score independent observations, validation and contradiction separately."""
    occurrences = max(0, int(occurrences or 0))
    validated_occurrences = max(0, int(validated_occurrences or 0))
    contradiction_count = max(0, int(contradiction_count or 0))
    occurrence_score = min(55, 15 + (occurrences * 10))
    validation_score = min(30, validated_occurrences * 15)
    contradiction_penalty = min(60, contradiction_count * 15)
    return max(0, min(100, occurrence_score + validation_score - contradiction_penalty))


def application_eligible(occurrences, confidence, contradiction_count=0):
    occurrences = max(0, int(occurrences or 0))
    confidence = max(0, int(confidence or 0))
    contradiction_count = max(0, int(contradiction_count or 0))
    if contradiction_count >= occurrences:
        return False
    return (occurrences >= 2 and confidence >= 60) or (
        occurrences >= 4 and confidence >= 55
    )


def _dedupe(values, limit=100):
    result = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result[-limit:]


def merge_llgr(existing, incoming, source_reference):
    """Merge one independently sourced observation into a canonical pattern."""
    merged = deepcopy(existing or {})
    incoming = deepcopy(incoming or {})
    source_reference = str(source_reference or "").strip()

    sources = _dedupe(merged.get("source_references", []))
    is_new_source = bool(source_reference and source_reference not in sources)
    if is_new_source:
        sources.append(source_reference)

    # Legacy occurrence totals have no source trail and cannot be treated as proof.
    if "legacy_occurrences" not in merged and not merged.get("source_references"):
        merged["legacy_occurrences"] = int(merged.get("occurrences") or 0)

    occurrences = len(sources)
    prior_validated = int(merged.get("validated_occurrences") or 0)
    validated_occurrences = prior_validated + (
        1 if is_new_source and incoming.get("validated") is True else 0
    )
    incoming_contradictions = int(incoming.get("contradiction_count") or 0)
    contradiction_count = int(merged.get("contradiction_count") or 0)
    if is_new_source:
        contradiction_count += incoming_contradictions

    lesson = str(incoming.get("lesson") or merged.get("lesson") or "").strip()
    confidence = calculate_confidence(
        occurrences, validated_occurrences, contradiction_count
    )
    governance = dict(merged.get("governance") or {})
    governance.update(incoming.get("governance") or {})
    full_cycle_complete = bool(
        governance.get("full_learning_cycle_complete") is True
        and governance.get("future_outcome_observed") is True
    )
    eligible = bool(
        full_cycle_complete
        and application_eligible(occurrences, confidence, contradiction_count)
    )

    for key, value in incoming.items():
        if key not in {"occurrences", "confidence", "confidence_score", "trend"}:
            merged[key] = value

    merged.update({
        "lesson": lesson,
        "lesson_fingerprint": lesson_fingerprint(lesson),
        "source_references": sources,
        "source_count": occurrences,
        "occurrences": occurrences,
        "validated_occurrences": validated_occurrences,
        "contradiction_count": contradiction_count,
        "confidence": confidence,
        "confidence_score": confidence,
        "trend": calculate_trend(occurrences),
        "pattern_status": "active" if eligible else "candidate",
        "application_eligible": eligible,
        "full_learning_cycle_complete": full_cycle_complete,
        "growth_stored": True,
        "durable_growth_stored": eligible,
        "last_seen_at": _now(),
    })
    merged.setdefault("first_seen_at", merged["last_seen_at"])
    merged["evidence"] = _dedupe(
        list((existing or {}).get("evidence", []) or [])
        + list(incoming.get("evidence", []) or [])
    )
    merged["contradiction_evidence"] = _dedupe(
        list((existing or {}).get("contradiction_evidence", []) or [])
        + list(incoming.get("contradiction_evidence", []) or [])
    )
    return merged, is_new_source


def store_llgr(llgr, source_reference=None, client=None):
    """Store a growth observation and return an auditable outcome."""
    lesson = str((llgr or {}).get("lesson") or "").strip()
    normalised = normalise_lesson(lesson)
    if not normalised or normalised in IGNORED_LESSONS:
        return {"stored": False, "reason": "non_specific_lesson"}
    if not source_reference:
        return {"stored": False, "reason": "missing_source_provenance"}

    database = client or _get_supabase()
    if database is None:
        return {"stored": False, "reason": "database_unavailable"}

    fingerprint = lesson_fingerprint(lesson)
    rows = (
        database.table("allegra_history")
        .select("id,stored_at,llgr")
        .order("stored_at", desc=True)
        .execute()
        .data
        or []
    )

    for row in rows:
        existing = row.get("llgr") or {}
        existing_fingerprint = existing.get("lesson_fingerprint") or lesson_fingerprint(
            existing.get("lesson")
        )
        if existing_fingerprint != fingerprint:
            continue

        merged, is_new_source = merge_llgr(existing, llgr, source_reference)
        if not is_new_source:
            return {
                "stored": False,
                "reason": "duplicate_source",
                "id": row.get("id"),
                "pattern": existing,
            }
        response = (
            database.table("allegra_history")
            .update({"llgr": merged})
            .eq("id", row["id"])
            .execute()
        )
        return {
            "stored": bool(response.data),
            "reason": "pattern_updated",
            "id": row.get("id"),
            "pattern": merged,
        }

    merged, _ = merge_llgr({}, llgr, source_reference)
    response = database.table("allegra_history").insert({"llgr": merged}).execute()
    rows = response.data or []
    return {
        "stored": bool(rows),
        "reason": "candidate_created",
        "id": rows[0].get("id") if rows else None,
        "pattern": merged,
    }
