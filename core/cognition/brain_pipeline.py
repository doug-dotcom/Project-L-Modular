import os
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from supabase import create_client

from memory.promotion.gate import (
    evaluate_promotion,
)
from memory.promotion.specialised import write_specialised_memories
from memory.retrieval.cache_state import invalidate_recall_caches
from core.cognition.memory_governance import build_memory_payload
from core.cognition.learning_engine import record_user_learning

load_dotenv(ROOT / ".env")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    or os.getenv("SUPABASE_KEY", "")
)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

RAW_TABLE = "raw_catchall"

def already_processed(table, raw_id):
    result = (
        supabase.table(table)
        .select("id")
        .eq("raw_id", raw_id)
        .limit(1)
        .execute()
    )

    return bool(result.data)


def process_raw_memory(row):
    promotion = evaluate_promotion(row)
    raw_id = row.get("id") if isinstance(row, dict) else None

    if not promotion["promote"]:
        return {
            "raw_id": raw_id,
            "status": "skipped",
            "reason": promotion["reason"],
            "target": None,
        }

    payload, governance = build_memory_payload(row, promotion)
    target_table = governance["carol"]["target_table"]

    if already_processed(target_table, raw_id):
        return {
            "raw_id": raw_id,
            "status": "skipped",
            "reason": "already_processed",
            "target": target_table,
        }

    supabase.table(target_table).insert(payload).execute()

    specialised = write_specialised_memories(
        supabase,
        row,
        category=target_table.removeprefix("memory_"),
    )
    learning = record_user_learning(row, client=supabase)
    invalidate_recall_caches(long_term=True)

    return {
        "raw_id": raw_id,
        "status": "processed",
        "target": target_table,
        "subjects": payload["subjects"],
        "values": payload["values"],
        "importance": payload["importance"],
        "salience": payload["salience"],
        "anchor": payload["anchor"],
        "specialised": specialised,
        "learning": learning,
        "governance": governance,
    }


def run(limit=2500):
    result = (
        supabase.table(RAW_TABLE)
        .select("*")
        .order("id", desc=True)
        .limit(limit)
        .execute()
    )

    rows = result.data or []
    rows.reverse()

    outcomes = []

    for row in rows:
        try:
            outcome = process_raw_memory(row)
            if outcome:
                outcomes.append(outcome)
        except Exception as e:
            outcomes.append({
                "raw_id": row.get("id"),
                "status": "error",
                "error": str(e),
            })

    return {
        "status": "ok",
        "checked": len(rows),
        "outcomes": outcomes,
    }


if __name__ == "__main__":
    result = run(limit=2500)

    print()
    print("=" * 50)
    print("PROJECT L GOVERNED MEMORY PIPELINE V3")
    print("=" * 50)
    print("Checked:", result["checked"])

    for item in result["outcomes"]:
        print(item)
