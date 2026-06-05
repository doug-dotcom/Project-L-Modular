import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from supabase import create_client

from memory.classifier.short_term_classifier import (
    classify_message
)

load_dotenv()

SUPABASE_URL = os.getenv(
    "SUPABASE_URL",
    ""
)

SUPABASE_KEY = (
    os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY",
        ""
    )
    or
    os.getenv(
        "SUPABASE_KEY",
        ""
    )
)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

BATCH_SIZE = 100

def load_raw_batch():

    result = (
        supabase.table(
            "raw_catchall"
        )
        .select("*")
        .order(
            "id",
            desc=False
        )
        .limit(
            BATCH_SIZE
        )
        .execute()
    )

    return result.data or []

def write_short_term(
    table_name,
    role,
    content
):

    (
        supabase.table(
            table_name
        )
        .insert({

            "role": role,
            "content": content

        })
        .execute()
    )

def run():

    rows = load_raw_batch()

    stats = {}

    for row in rows:

        content = str(
            row.get(
                "content",
                ""
            )
        )

        role = str(
            row.get(
                "role",
                "unknown"
            )
        )

        if not content:
            continue

        domain = classify_message(
            content
        )

        write_short_term(

            domain,

            role,

            content

        )

        stats[domain] = (
            stats.get(
                domain,
                0
            ) + 1
        )

    print()
    print("=" * 40)
    print("RAW CATCHALL MIGRATION COMPLETE")
    print("=" * 40)
    print()

    total = 0

    for k, v in sorted(stats.items()):

        print(
            f"{k}: {v}"
        )

        total += v

    print()
    print(
        f"TOTAL: {total}"
    )

if __name__ == "__main__":

    run()
