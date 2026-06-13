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

SUPABASE_URL = os.getenv(
    "SUPABASE_URL"
)

SUPABASE_KEY = (
    os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY"
    )
    or
    os.getenv(
        "SUPABASE_KEY"
    )
)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

# =====================================================
# MEMORY FILTER
# =====================================================

def is_memory_worthy(content):

    text = str(
        content
    ).lower().strip()

    junk_starts = [

        "hello",
        "hey",
        "hi",
        "good morning",
        "good night",
        "awesome",
        "boom",
        "thank you",
        "great work"

    ]

    for item in junk_starts:

        if text.startswith(item):
            return False

    junk_contains = [

        "calendar",
        "appointment",
        "meeting",
        "ai error",
        "error code 429"

    ]

    for item in junk_contains:

        if item in text:
            return False

    if len(text) < 20:
        return False

    return True

# =====================================================
# PROCESS RANGE
# =====================================================

def process_range(
    start,
    end
):

    rows = (
        supabase
        .table(
            "raw_catchall"
        )
        .select("*")
        .gte(
            "id",
            start
        )
        .lte(
            "id",
            end
        )
        .order(
            "id"
        )
        .execute()
    ).data or []

    processed = 0
    skipped = 0
    filtered = 0

    for row in rows:

        content = row.get(
            "content",
            ""
        )

        if not is_memory_worthy(
            content
        ):

            filtered += 1
            continue

        result = process_raw_memory(
            row
        )

        if result:

            if (
                result["status"]
                ==
                "processed"
            ):
                processed += 1

            elif (
                result["status"]
                ==
                "skipped"
            ):
                skipped += 1

    print()
    print("=" * 50)
    print(
        f"RANGE {start}-{end}"
    )
    print("=" * 50)
    print(
        f"processed={processed}"
    )
    print(
        f"skipped={skipped}"
    )
    print(
        f"filtered={filtered}"
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
    print("=" * 50)
    print(
        "CLEAN BACKFILL COMPLETE"
    )
    print("=" * 50)


