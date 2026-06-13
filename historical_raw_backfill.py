import os
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from supabase import create_client

from core.cognition.brain_pipeline import (
    process_raw_memory
)

load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")

SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or
    os.getenv("SUPABASE_KEY")
)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

RAW_TABLE = "raw_catchall"

# =====================================================
# FETCH RANGE
# =====================================================

def process_range(
    start,
    end
):

    rows = (
        supabase
        .table(RAW_TABLE)
        .select("*")
        .gte("id", start)
        .lte("id", end)
        .order("id")
        .execute()
    ).data or []

    print()
    print("=" * 60)
    print(f"PROCESSING {start} -> {end}")
    print(f"ROWS FOUND: {len(rows)}")
    print("=" * 60)

    processed = 0
    skipped = 0
    errors = 0

    for row in rows:

        try:

            result = process_raw_memory(
                row
            )

            if not result:
                continue

            if result["status"] == "processed":
                processed += 1

            elif result["status"] == "skipped":
                skipped += 1

        except Exception as e:

            errors += 1

            print(
                f"ERROR {row.get('id')}: {e}"
            )

    print()
    print(
        f"processed={processed}"
    )

    print(
        f"skipped={skipped}"
    )

    print(
        f"errors={errors}"
    )

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":

    process_range(
        1,
        1000
    )

    process_range(
        1001,
        2000
    )

    process_range(
        2001,
        3019
    )

    print()
    print("=" * 60)
    print("AODS 18 COMPLETE")
    print("=" * 60)
