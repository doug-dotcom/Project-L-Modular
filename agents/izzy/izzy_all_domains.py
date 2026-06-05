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

def process_table(table):

    result = (
        supabase.table(table)
        .select("*")
        .execute()
    )

    rows = result.data or []

    updated = 0

    for row in rows:

        processed = (
            row.get(
                "processed_by",
                []
            )
            or []
        )

        if "izzy" in processed:
            continue

        processed.append(
            "izzy"
        )

        (
            supabase.table(table)
            .update({

                "values": [],
                "preferences": [],
                "processed_by": processed

            })
            .eq("id", row["id"])
            .execute()
        )

        updated += 1

    return updated

def run():

    total = 0

    for table in TABLES:

        count = process_table(table)

        print(
            f"{table}: {count}"
        )

        total += count

    return {

        "status":"ok",
        "updated":total

    }

if __name__ == "__main__":

    print(
        run()
    )
