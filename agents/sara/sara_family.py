import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL","")

SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY","")
    or
    os.getenv("SUPABASE_KEY","")
)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

TABLE = "memory_family"

def run_sara_family(limit=25):

    result = (
        supabase.table(TABLE)
        .select("*")
        .order("id", desc=True)
        .limit(limit)
        .execute()
    )

    rows = result.data or []

    updated = 0

    for row in rows:

        processed = row.get(
            "processed_by",
            []
        ) or []

        if "sara" in processed:
            continue

        processed.append(
            "sara"
        )

        (
            supabase.table(TABLE)
            .update({

                "importance": 50,

                "salience": 50,

                "anchor": False,

                "processed_by": processed

            })
            .eq("id", row["id"])
            .execute()
        )

        updated += 1

    return {
        "status":"ok",
        "table":TABLE,
        "updated":updated
    }

if __name__ == "__main__":
    print(
        run_sara_family()
    )
