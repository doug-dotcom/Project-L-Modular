import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import os
from dotenv import load_dotenv
from supabase import create_client
from agents.allegra.growth_retrieval import retrieve_growth_context

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")

SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    or os.getenv("SUPABASE_KEY", "")
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

ENTITY_TABLE_MAP = {
    "iyla": "memory_family",
    "ashton": "memory_family",
    "luella": "memory_family",
    "mehlia": "memory_family",

    "cass": "memory_relationships",
    "leah": "memory_relationships",
    "tamara": "memory_relationships",

    "project l": "memory_project_l",
    "brains trust": "memory_project_l",
    "carol": "memory_project_l",
    "sara": "memory_project_l",
    "mary": "memory_project_l",
    "izzy": "memory_project_l",
    "rachel": "memory_project_l",

    "recovery": "memory_recovery",
    "na": "memory_recovery",
    "aa": "memory_recovery",

    "health": "memory_health",
    "weight": "memory_health",
    "sleep": "memory_health",

    "hockey": "memory_sport",
    "sport": "memory_sport"
}


def detect_entities(query):
    text = str(query).lower()
    found = []

    for entity, table in ENTITY_TABLE_MAP.items():
        if entity in text:
            found.append({
                "entity": entity,
                "preferred_table": table
            })

    return found


def score_memory(row, query, table, entities):
    content = str(
        row.get(
            "content",
            ""
        )
    ).lower()

    primary_subject = str(
        row.get(
            "primary_subject",
            ""
        )
    ).lower()

    subjects = (
        row.get(
            "subjects",
            []
        )
        or
        []
    )

    subjects = [
        str(x).lower()
        for x in subjects
    ]

    query = str(query).lower()

    score = 0

    if query == primary_subject:
        score += 1000

    if query in subjects:
        score += 750

    for word in query.split():
        if word and word in content:
            score += 25

    for item in entities:
        entity = item["entity"]
        preferred_table = item["preferred_table"]

        if table == preferred_table:
            score += 500

        if entity in content:
            score += 300

    score += int(row.get("importance") or 0)
    score += int(row.get("salience") or 0)

    if row.get("anchor") is True:
        score += 100

    processed = row.get("processed_by") or []
    score += len(processed) * 10

    return score


def retrieve(query, limit=10):
    results = []
    entities = detect_entities(query)

    for table in TABLES:
        rows = (
            supabase.table(table)
            .select("*")
            .execute()
        ).data or []

        for row in rows:
            score = score_memory(
                row,
                query,
                table,
                entities
            )

            if score <= 0:
                continue

            results.append({
                "table": table,
                "score": score,
                "content": row.get("content", ""),
                "primary_subject": row.get("primary_subject", ""),
                "subjects": row.get("subjects", []),
                "importance": row.get("importance", 0),
                "salience": row.get("salience", 0),
                "anchor": row.get("anchor", False),
                "processed_by": row.get("processed_by", [])
            })

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results[:limit]


def build_context_packet(query):
    entities = detect_entities(query)
    matches = retrieve(query, limit=10)

    packet = []
    packet.append("RELEVANT MEMORY CONTEXT")
    packet.append("=" * 30)
    packet.append("Query: " + str(query))

    if entities:
        packet.append("")
        packet.append("Detected entities:")
        for item in entities:
            packet.append(
                "- "
                + item["entity"]
                + " -> "
                + item["preferred_table"]
            )

    growth = retrieve_growth_context()

    packet.append("")
    packet.append("RELEVANT GROWTH CONTEXT")
    packet.append("=" * 30)

    if growth:

        for lesson in growth:

            packet.append(
                "• " + str(lesson)
            )

    packet.append("")
    packet.append("Matches: " + str(len(matches)))

    for i, m in enumerate(matches, 1):
        packet.append("")
        packet.append(
            f"{i}. [{m['table']}] score={m['score']}"
        )
        packet.append(
            f"primary_subject={m['primary_subject']} subjects={m['subjects']}"
        )
        packet.append(
            f"importance={m['importance']} salience={m['salience']} anchor={m['anchor']}"
        )
        packet.append(
            "processed_by=" + str(m["processed_by"])
        )
        packet.append(
            str(m["content"])[:300]
        )

    return "\n".join(packet)


if __name__ == "__main__":
    query = input("Context Query: ")
    print()
    print(build_context_packet(query))

