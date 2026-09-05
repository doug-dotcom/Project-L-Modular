"""Retrieve only applicable, query-relevant Allegra growth patterns."""

from __future__ import annotations

import os
import re

from dotenv import load_dotenv
from supabase import create_client

from agents.allegra.llgr_storage import (
    application_eligible,
    calculate_confidence,
    calculate_trend,
    normalise_lesson,
)


load_dotenv()

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "do", "for", "from", "how",
    "i", "in", "is", "it", "me", "my", "of", "on", "or", "that", "the",
    "this", "to", "was", "what", "when", "where", "who", "why", "with", "you",
}


def _get_supabase():
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_KEY", "")
    return create_client(url, key) if url and key else None


def _tokens(value):
    return {
        token for token in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if len(token) > 2 and token not in STOP_WORDS
    }


def _normalise_record(row):
    llgr = dict((row or {}).get("llgr") or {})
    lesson = str(llgr.get("lesson") or "").strip()
    if not normalise_lesson(lesson):
        return None

    sources = list(llgr.get("source_references") or [])
    # Untraceable legacy totals are one candidate, not N independent observations.
    occurrences = len(sources) if sources else 1
    validated_occurrences = int(llgr.get("validated_occurrences") or 0)
    if not sources and llgr.get("validated") is True:
        validated_occurrences = 1
    contradictions = int(llgr.get("contradiction_count") or 0)
    confidence = calculate_confidence(
        occurrences, validated_occurrences, contradictions
    )
    governance = llgr.get("governance") or {}
    full_cycle_complete = bool(
        governance.get("full_learning_cycle_complete") is True
        and governance.get("future_outcome_observed") is True
    )
    eligible = bool(
        full_cycle_complete
        and application_eligible(occurrences, confidence, contradictions)
    )

    return {
        "id": row.get("id"),
        "stored_at": row.get("stored_at"),
        "lesson": lesson,
        "adjustment": str(llgr.get("adjustment") or "").strip(),
        "reflection": llgr.get("reflection") or [],
        "occurrences": occurrences,
        "confidence": confidence,
        "trend": calculate_trend(occurrences),
        "application_eligible": eligible,
        "full_learning_cycle_complete": full_cycle_complete,
        "source_references": sources,
        "contradiction_count": contradictions,
    }


def _relevance(record, query):
    query_tokens = _tokens(query)
    if not query_tokens:
        return 1
    haystack = " ".join([
        record.get("lesson", ""),
        record.get("adjustment", ""),
        " ".join(str(item) for item in record.get("reflection", []) or []),
    ])
    return len(query_tokens & _tokens(haystack))


def retrieve_growth_records(query="", limit=8, client=None):
    database = client or _get_supabase()
    if database is None:
        return []

    result = (
        database.table("allegra_history")
        .select("id,stored_at,llgr")
        .order("stored_at", desc=True)
        .limit(100)
        .execute()
    )

    records = []
    for row in result.data or []:
        record = _normalise_record(row)
        if not record or not record["application_eligible"]:
            continue
        relevance = _relevance(record, query)
        if query and relevance <= 0:
            continue
        record["relevance"] = relevance
        records.append(record)

    records.sort(
        key=lambda record: (
            record["relevance"], record["confidence"], record["occurrences"],
            str(record.get("stored_at") or ""),
        ),
        reverse=True,
    )
    return records[: max(0, int(limit))]


def retrieve_growth_context(query="", limit=8, client=None):
    lines = []
    for record in retrieve_growth_records(query=query, limit=limit, client=client):
        provenance = ", ".join(record["source_references"][:3]) or "legacy-unverified"
        adjustment = f" Action: {record['adjustment']}" if record["adjustment"] else ""
        lines.append(
            f"{record['lesson']} (confidence {record['confidence']}%, "
            f"{record['occurrences']} independent sources, {record['trend']}; "
            f"provenance: {provenance}).{adjustment}"
        )
    return lines
