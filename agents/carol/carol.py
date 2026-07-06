import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

# =====================================================
# CAROL V3
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


def memory_status(content):

    content = clean_content(content)

    if not content:
        return "NOISE"

    if len(content) < 10:
        return "NOISE"

    return "ACTIVE"


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

        return False


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

        raw_id = row.get("id")

        if already_exists(
            target_table,
            raw_id
        ):
            skipped += 1
            continue

        content = clean_content(
            row.get("content", "")
        )

        status = memory_status(
            content
        )

        payload = {

            "raw_id": raw_id,

            "content": content,

            "importance": 50,

            "salience": 50,

            "anchor": False,

            "memory_status": status,

            "processed_by": [
                "carol_v3"
            ],

            "metadata": {

                "source_table": source_table,

                "carol_version": "3.0",

                "processed_at": datetime.now().isoformat()

            }

        }

        supabase.table(
            target_table
        ).insert(
            payload
        ).execute()

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
