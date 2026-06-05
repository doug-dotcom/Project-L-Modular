import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")

SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    or
    os.getenv("SUPABASE_KEY", "")
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

    content = str(row.get("content", "")).lower()
    query = str(query).lower()

    score = 0

    # keyword match
    for word in query.split():
        if word and word in content:
            score += 25

    # Sara layer
    score += int(row.get("importance") or 0)
    score += int(row.get("salience") or 0)

    # anchor boost
    if row.get("anchor") is True:
        score += 100

    # Brains Trust completion boost
    processed = row.get("processed_by") or []
    score += len(processed) * 10

    return score

def search_memories(query, limit=20):

    results = []

    for table in TABLES:

        data = (
            supabase.table(table)
            .select("*")
            .execute()
        )

        rows = data.data or []

        for row in rows:

            score = score_memory(row, query)

            if score <= 0:
                continue

            results.append({
                "table": table,
                "score": score,
                "content": row.get("content", ""),
                "importance": row.get("importance", 0),
                "salience": row.get("salience", 0),
                "anchor": row.get("anchor", False),
                "processed_by": row.get("processed_by", [])
            })

    results.sort(
        key=lambda x: x.get("score", 0),
        reverse=True
    )

    return results[:limit]

if __name__ == "__main__":

    query = input("Search: ")

    matches = search_memories(query)

    print()
    print("=" * 40)
    print("CAPTAIN RACHEL RANKED RESULTS")
    print("=" * 40)

    for i, m in enumerate(matches, 1):

        print()
        print(f"{i}. {m['table']} | score: {m['score']}")
        print(f"importance: {m['importance']} | salience: {m['salience']} | anchor: {m['anchor']}")
        print(f"processed_by: {m['processed_by']}")
        print(m["content"][:250])
