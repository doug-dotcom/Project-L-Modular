# =====================================================
# AODS 17.5
# FULL HISTORICAL GROWTH REPLAY
# =====================================================

import os
import sys
import json
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.coach.mary_coach_adapter import run_memory_to_coach

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

MEMORY_TABLES = [
    "memory_family",
    "memory_identity",
    "memory_recovery",
    "memory_relationships",
    "memory_project_l",
    "memory_health",
    "memory_sport",
    "memory_work",
    "memory_general",
]

STATE_DIR = ROOT / "data"
STATE_DIR.mkdir(exist_ok=True)

CHECKPOINT_FILE = STATE_DIR / "aods_17_5_growth_replay_checkpoint.json"
ERROR_FILE = STATE_DIR / "aods_17_5_growth_replay_errors.json"

PAGE_SIZE = 100


def load_checkpoint():

    if CHECKPOINT_FILE.exists():

        try:
            return set(
                json.loads(
                    CHECKPOINT_FILE.read_text(
                        encoding="utf-8"
                    )
                )
            )

        except Exception:
            return set()

    return set()


def save_checkpoint(processed):

    CHECKPOINT_FILE.write_text(
        json.dumps(
            sorted(list(processed)),
            indent=2
        ),
        encoding="utf-8"
    )


def log_error(error_record):

    errors = []

    if ERROR_FILE.exists():

        try:
            errors = json.loads(
                ERROR_FILE.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:
            errors = []

    errors.append(error_record)

    ERROR_FILE.write_text(
        json.dumps(
            errors,
            indent=2
        ),
        encoding="utf-8"
    )


def fetch_page(table, start, end):

    result = (
        supabase
        .table(table)
        .select("*")
        .range(start, end)
        .execute()
    )

    return result.data or []


def replay_table(table, processed):

    print()
    print("=" * 60)
    print(f"REPLAYING TABLE: {table}")
    print("=" * 60)

    start = 0
    total_processed = 0
    total_skipped = 0
    total_errors = 0

    while True:

        end = start + PAGE_SIZE - 1

        rows = fetch_page(
            table,
            start,
            end
        )

        if not rows:
            break

        for row in rows:

            row_id = row.get("id")

            key = f"{table}:{row_id}"

            if key in processed:

                total_skipped += 1
                continue

            try:

                memory = {
                    "content": row.get("content", ""),
                    "subjects": row.get("subjects", []),
                    "values": row.get("values", []),
                    "patterns": row.get("patterns", []),
                    "relationships": row.get("relationships", []),
                    "importance": row.get("importance", 0),
                    "salience": row.get("salience", 0),
                    "anchor": row.get("anchor", False),
                }

                if not memory["content"]:

                    processed.add(key)
                    total_skipped += 1
                    continue

                run_memory_to_coach(
                    memory
                )

                processed.add(key)
                total_processed += 1

                if total_processed % 25 == 0:

                    save_checkpoint(
                        processed
                    )

                    print(
                        f"{table}: processed={total_processed} skipped={total_skipped} errors={total_errors}"
                    )

            except Exception as e:

                total_errors += 1

                log_error({
                    "timestamp": datetime.now().isoformat(),
                    "table": table,
                    "id": row_id,
                    "error": str(e),
                })

        save_checkpoint(
            processed
        )

        start += PAGE_SIZE

    print(
        f"TABLE COMPLETE: {table} | processed={total_processed} skipped={total_skipped} errors={total_errors}"
    )

    return {
        "table": table,
        "processed": total_processed,
        "skipped": total_skipped,
        "errors": total_errors,
    }


def run():

    processed = load_checkpoint()

    summary = []

    print()
    print("=" * 60)
    print("AODS 17.5 HISTORICAL GROWTH REPLAY STARTED")
    print("=" * 60)
    print(f"Checkpoint loaded: {len(processed)} already processed")

    for table in MEMORY_TABLES:

        try:

            result = replay_table(
                table,
                processed
            )

            summary.append(
                result
            )

        except Exception as e:

            log_error({
                "timestamp": datetime.now().isoformat(),
                "table": table,
                "id": None,
                "error": str(e),
            })

            summary.append({
                "table": table,
                "processed": 0,
                "skipped": 0,
                "errors": 1,
            })

    print()
    print("=" * 60)
    print("AODS 17.5 HISTORICAL GROWTH REPLAY COMPLETE")
    print("=" * 60)

    for item in summary:

        print(
            f"{item['table']}: processed={item['processed']} skipped={item['skipped']} errors={item['errors']}"
        )

    print()
    print(f"Checkpoint: {CHECKPOINT_FILE}")
    print(f"Errors: {ERROR_FILE}")


if __name__ == "__main__":

    run()
