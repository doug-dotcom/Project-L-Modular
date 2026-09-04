import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client
from memory.promotion.gate import evaluate_promotion
from memory.promotion.specialised import write_specialised_memories
from memory.retrieval.cache_state import invalidate_recall_caches

# =====================================================
# CAROL V4
# MEMORY CURATOR
# =====================================================

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

# =====================================================
# DOMAIN MAP
# =====================================================

DOMAINS = [

    ("short_term_family", "memory_family"),

    ("short_term_health", "memory_health"),

    ("short_term_identity", "memory_identity"),

    ("short_term_project_l", "memory_project_l"),

    ("short_term_recovery", "memory_recovery"),

    ("short_term_relationships", "memory_relationships"),

    ("short_term_sport", "memory_sport"),

    ("short_term_work", "memory_work"),

]

# =====================================================
# HELPERS
# =====================================================

def clean_content(text):

    return str(text or "").strip()


def resolve_raw_source(short_term_row):

    content = clean_content(
        short_term_row.get("content", "")
    )

    role = clean_content(
        short_term_row.get("role", "")
    ).lower()

    if not content or not role:
        return None

    try:

        result = (
            supabase
            .table("raw_catchall")
            .select("*")
            .eq("role", role)
            .eq("content", content)
            .order("id", desc=True)
            .limit(1)
            .execute()
        )

        rows = result.data or []

        return rows[0] if rows else None

    except Exception:

        return None


def already_exists(
    target_table,
    raw_id
):

    try:

        result = (
            supabase
            .table(target_table)
            .select("id")
            .eq("raw_id", raw_id)
            .limit(1)
            .execute()
        )

        return bool(result.data)

    except Exception:

        return None


# =====================================================
# PROCESS DOMAIN
# =====================================================

def process_domain(

    source_table,
    target_table,
    limit=100

):

    result = (

        supabase
        .table(source_table)
        .select("*")
        .order("id", desc=True)
        .limit(limit)
        .execute()

    )

    rows = result.data or []

    rows.reverse()

    moved = 0
    skipped = 0

    for row in rows:

        raw_row = resolve_raw_source(row)

        promotion = evaluate_promotion(raw_row)

        if not promotion["promote"]:
            skipped += 1
            continue

        raw_id = raw_row.get("id")

        existing = already_exists(
            target_table,
            raw_id
        )

        if existing is None:
            skipped += 1
            continue

        if existing:
            skipped += 1
            continue

        content = clean_content(
            raw_row.get("content", "")
        )

        payload = {

            "raw_id": raw_id,

            "content": content,

            "importance": 50,

            "salience": 50,

            "anchor": False,

            "memory_status": "ACTIVE",

            "processed_by": [
                "carol_v4"
            ],

            "metadata": {

                "source_table": "raw_catchall",

                "source_short_term_table": source_table,

                "carol_version": "4.0",

                "promotion_gate": {

                    "version": "2.0",

                    "reason": promotion["reason"],

                    "explicit": promotion["explicit"],

                    "source_role": clean_content(
                        raw_row.get("role", "")
                    ).lower()

                },

                "processed_at": datetime.now().isoformat()

            }

        }

        supabase.table(
            target_table
        ).insert(
            payload
        ).execute()

        write_specialised_memories(
            supabase,
            raw_row,
            category=target_table.removeprefix("memory_"),
        )

        invalidate_recall_caches(long_term=True)

        moved += 1

    return {

        "source": source_table,

        "target": target_table,

        "moved": moved,

        "skipped": skipped

    }


# =====================================================
# RUN ALL
# =====================================================

def run_carol():

    report = []

    total_moved = 0

    total_skipped = 0

    for source_table, target_table in DOMAINS:

        result = process_domain(

            source_table,

            target_table

        )

        report.append(
            result
        )

        total_moved += result["moved"]

        total_skipped += result["skipped"]

    return {

        "status": "ok",

        "domains": len(DOMAINS),

        "moved": total_moved,

        "skipped": total_skipped,

        "report": report

    }


if __name__ == "__main__":

    print()

    print("=" * 60)
    print("CAROL V3")
    print("=" * 60)

    print(
        run_carol()
    )
