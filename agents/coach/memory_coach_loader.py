import os
import sys
import json

from pathlib import Path
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

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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

CHECKPOINT_PATH = ROOT / "data" / "coach_memory_checkpoint.json"

MAX_PER_TABLE = 25


def load_checkpoint():
    if CHECKPOINT_PATH.exists():
        try:
            return set(json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8")))
        except Exception:
            return set()

    return set()


def save_checkpoint(done):
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(
        json.dumps(sorted(list(done)), indent=2),
        encoding="utf-8"
    )


def fetch_memories(table):
    result = (
        supabase
        .table(table)
        .select("*")
        .order("raw_id")
        .limit(MAX_PER_TABLE)
        .execute()
    )

    return result.data or []


def run():
    done = load_checkpoint()

    processed = 0
    skipped = 0
    errors = 0

    print()
    print("=" * 60)
    print("MEMORY -> COACH -> ALLEGRA STARTED")
    print("=" * 60)

    for table in MEMORY_TABLES:

        rows = fetch_memories(table)

        print()
        print("=" * 60)
        print(f"TABLE: {table} | rows={len(rows)}")
        print("=" * 60)

        for memory in rows:

            raw_id = memory.get("raw_id")
            memory_id = memory.get("id")

            key = f"{table}:{raw_id or memory_id}"

            if key in done:
                skipped += 1
                continue

            try:
                print(f"Processing {key}")

                run_memory_to_coach(memory)

                done.add(key)
                save_checkpoint(done)

                processed += 1

            except Exception as e:
                errors += 1
                print(f"ERROR {key}: {e}")

    print()
    print("=" * 60)
    print("MEMORY -> COACH -> ALLEGRA COMPLETE")
    print("=" * 60)
    print(f"processed={processed}")
    print(f"skipped={skipped}")
    print(f"errors={errors}")
    print("=" * 60)


if __name__ == "__main__":
    run()
