import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

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

def search_memories(
    query,
    limit=20
):

    query = str(
        query
    ).lower()

    results = []

    for table in TABLES:

        data = (
            supabase.table(table)
            .select("*")
            .execute()
        )

        rows = data.data or []

        for row in rows:

            content = str(
                row.get(
                    "content",
                    ""
                )
            ).lower()

            if query in content:

                results.append({

                    "table": table,
                    "content": row.get(
                        "content",
                        ""
                    ),
                    "importance": row.get(
                        "importance",
                        0
                    )

                })

    return results[:limit]

if __name__ == "__main__":

    query = input(
        "Search: "
    )

    matches = search_memories(
        query
    )

    print()
    print("=" * 40)
    print("CAPTAIN RACHEL")
    print("=" * 40)

    for m in matches:

        print()
        print(
            m["table"]
        )

        print(
            m["content"][:150]
        )
