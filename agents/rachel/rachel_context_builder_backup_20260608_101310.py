import os

from dotenv import load_dotenv
from supabase import create_client

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

def score_memory(row, query):

    content = str(
        row.get(
            "content",
            ""
        )
    ).lower()

    score = 0

    for word in query.lower().split():

        if word in content:
            score += 25

    score += int(
        row.get(
            "importance",
            0
        ) or 0
    )

    score += int(
        row.get(
            "salience",
            0
        ) or 0
    )

    if row.get("anchor") is True:
        score += 100

    processed = (
        row.get(
            "processed_by",
            []
        )
        or []
    )

    score += len(processed) * 10

    return score

def retrieve(query, limit=10):

    results = []

    for table in TABLES:

        rows = (
            supabase.table(table)
            .select("*")
            .execute()
        ).data or []

        for row in rows:

            score = score_memory(row, query, table)

            if score <= 0:
                continue

            results.append({

                "table": table,
                "score": score,
                "content": row.get(
                    "content",
                    ""
                )

            })

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results[:limit]

def build_context_packet(query):

    matches = retrieve(
        query,
        limit=10
    )

    packet = []

    packet.append(
        "RELEVANT MEMORY CONTEXT"
    )

    packet.append(
        "=" * 30
    )

    for i, m in enumerate(matches, 1):

        packet.append("")

        packet.append(
            f"{i}. [{m['table']}] score={m['score']}"
        )

        packet.append(
            str(
                m["content"]
            )[:300]
        )

    return "\n".join(packet)

if __name__ == "__main__":

    query = input(
        "Context Query: "
    )

    print()

    print(
        build_context_packet(
            query
        )
    )

