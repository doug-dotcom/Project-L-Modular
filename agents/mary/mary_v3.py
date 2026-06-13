# =====================================================
# AODS 9 - MARY V3
# SUPABASE MEANING PACKETS
# =====================================================

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")

SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    or os.getenv("SUPABASE_KEY", "")
)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


TABLES = [
    "memory_family",
    "memory_identity",
    "memory_recovery",
    "memory_relationships",
    "memory_project_l",
    "memory_health",
    "memory_sport",
    "memory_work"
]


VALUE_KEYWORDS = {
    "family": ["family", "kids", "children", "daughter", "son", "dad", "mum"],
    "growth": ["growth", "learn", "lesson", "reflection", "improve", "realised", "realized"],
    "truth": ["truth", "honest", "evidence", "facts", "real"],
    "recovery": ["recovery", "meeting", "aa", "na", "sober", "sobriety"],
    "protection": ["protect", "safe", "safety", "guardian"],
    "service": ["help", "support", "serve", "service"],
    "agency": ["keys", "ownership", "choice", "decision", "agency"]
}


PATTERN_KEYWORDS = {
    "validation seeking": ["validation", "approval", "certainty", "reassurance"],
    "self trust": ["trust myself", "self trust", "confidence"],
    "protection pattern": ["protect", "safe", "guardian"],
    "growth loop": ["lesson", "reflection", "adjustment", "growth"],
    "emotional processing": ["feel", "felt", "emotion", "cry", "leaking"],
    "project l development": ["project l", "mary", "coach", "learning loopers", "brains trust"]
}


RELATIONSHIP_KEYWORDS = {
    "Iyla": ["iyla"],
    "Ashton": ["ashton", "ash"],
    "Luella": ["luella"],
    "Mehlia": ["mehlia", "malia"],
    "Leah": ["leah"],
    "Cass": ["cass"],
    "Tamara": ["tamara"],
    "Pauline": ["pauline"],
    "Ken": ["ken"],
    "Mum": ["mum", "mother"],
    "Dad": ["dad", "father"]
}


def _safe_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _find_matches(text, mapping):
    found = []
    lower = text.lower()

    for label, keywords in mapping.items():
        if any(keyword in lower for keyword in keywords):
            found.append(label)

    return found


def _identity_relevance(text, values, patterns, relationships):
    score = 0
    lower = text.lower()

    score += len(values) * 10
    score += len(patterns) * 15
    score += len(relationships) * 8

    identity_terms = [
        "i am",
        "i'm",
        "my values",
        "who i am",
        "identity",
        "purpose",
        "believe",
        "trust myself",
        "confidence",
        "growth"
    ]

    for term in identity_terms:
        if term in lower:
            score += 10

    return min(score, 100)


def _build_meaning(content, values, patterns, relationships):
    if patterns:
        return f"Memory indicates a pattern of {patterns[0]}."

    if values:
        return f"Memory appears connected to the value of {values[0]}."

    if relationships:
        return f"Memory appears connected to relationship context involving {relationships[0]}."

    return "Memory contains context that may be meaningful after further processing."


def create_meaning_packet(row, table):
    content = _safe_text(row.get("content", ""))

    values = _find_matches(content, VALUE_KEYWORDS)
    patterns = _find_matches(content, PATTERN_KEYWORDS)
    relationships = _find_matches(content, RELATIONSHIP_KEYWORDS)

    identity_relevance = _identity_relevance(
        content,
        values,
        patterns,
        relationships
    )

    meaning = _build_meaning(
        content,
        values,
        patterns,
        relationships
    )

    growth_candidate = bool(
        values
        or patterns
        or identity_relevance >= 40
    )

    return {
        "memory_id": row.get("id"),
        "domain_table": table,
        "meaning": meaning,
        "values": values,
        "patterns": patterns,
        "relationships": relationships,
        "identity_relevance": identity_relevance,
        "growth_candidate": growth_candidate,
        "processed_at": datetime.now().isoformat()
    }


def process_table(table, limit=25):
    rows = (
        supabase.table(table)
        .select("*")
        .limit(limit)
        .execute()
    ).data or []

    updated = 0
    packets = []

    for row in rows:
        processed = row.get("processed_by") or []

        if "mary_v3" in processed:
            continue

        packet = create_meaning_packet(row, table)

        processed.append("mary_v3")

        supabase.table(table).update({
            "values": packet["values"],
            "patterns": packet["patterns"],
            "relationships": packet["relationships"],
            "processed_by": processed
        }).eq("id", row["id"]).execute()

        packets.append(packet)
        updated += 1

    return {
        "table": table,
        "updated": updated,
        "packets": packets
    }


def run_mary_v3(limit_per_table=25):
    results = []
    total_updated = 0

    print()
    print("=" * 45)
    print("AODS 9 - MARY V3 MEANING PACKETS")
    print("=" * 45)

    for table in TABLES:
        result = process_table(table, limit_per_table)
        results.append(result)
        total_updated += result["updated"]

        print(f"{table}: updated={result['updated']}")

    print("=" * 45)
    print(f"TOTAL UPDATED: {total_updated}")
    print("=" * 45)

    return {
        "agent": "Mary V3",
        "aods": "AODS 9",
        "status": "ok",
        "total_updated": total_updated,
        "results": results
    }


if __name__ == "__main__":
    run_mary_v3(limit_per_table=100)


