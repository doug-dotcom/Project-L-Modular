from supabase import create_client
from dotenv import load_dotenv

import os
import json

# =====================================================
# RHEE V2
# CHIEF RECALL OFFICER
# FULL MEMORY PAGINATION ENGINE
# =====================================================

# =====================================================
# ENV / SUPABASE
# =====================================================

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

# =====================================================
# MEMORY TABLES
# =====================================================

TABLES = [

    "memory_family",
    "memory_identity",
    "memory_relationships",
    "memory_recovery",
    "memory_health",
    "memory_project_l",
    "memory_general",
    "episodic_memories",
    "identity_anchors"

]

# =====================================================
# SAFE HELPERS
# =====================================================

def safe_int(
    value,
    default=0
):

    try:

        if value is None:
            return default

        return int(value)

    except Exception:

        return default


def safe_list(
    value
):

    if isinstance(
        value,
        list
    ):
        return value

    if value is None:
        return []

    if isinstance(
        value,
        str
    ):

        try:

            parsed = json.loads(
                value
            )

            if isinstance(
                parsed,
                list
            ):
                return parsed

        except Exception:

            return [
                value
            ]

    return []


def safe_text(
    value
):

    if value is None:
        return ""

    return str(
        value
    ).strip()


# =====================================================
# SCORING
# =====================================================

def calculate_memory_score(
    memory,
    query=""
):

    score = 0

    query_lower = safe_text(
        query
    ).lower()

    content_lower = safe_text(
        memory.get(
            "content",
            ""
        )
    ).lower()

    primary_subject = safe_text(
        memory.get(
            "primary_subject",
            ""
        )
    ).lower()

    # =================================================
    # BASE IMPORTANCE / SALIENCE
    # =================================================

    score += safe_int(
        memory.get(
            "importance",
            0
        )
    )

    score += safe_int(
        memory.get(
            "salience",
            0
        )
    )

    # =================================================
    # ANCHOR BOOST
    # =================================================

    if memory.get(
        "anchor",
        False
    ):
        score += 75

    # =================================================
    # PRIMARY SUBJECT
    # =================================================

    if (
        query_lower
        and primary_subject
        and query_lower in primary_subject
    ):
        score += 100

    # =================================================
    # SUBJECTS
    # =================================================

    subjects = safe_list(
        memory.get(
            "subjects",
            []
        )
    )

    for subject in subjects:

        subject_lower = safe_text(
            subject
        ).lower()

        if (
            query_lower
            and subject_lower
            and query_lower in subject_lower
        ):
            score += 50

    # =================================================
    # RELATIONSHIPS
    # =================================================

    relationships = safe_list(
        memory.get(
            "relationships",
            []
        )
    )

    for relationship in relationships:

        relationship_lower = safe_text(
            relationship
        ).lower()

        if (
            query_lower
            and relationship_lower
            and query_lower in relationship_lower
        ):
            score += 40

    # =================================================
    # VALUES
    # =================================================

    values = safe_list(
        memory.get(
            "values",
            []
        )
    )

    score += (
        len(values) * 5
    )

    for value in values:

        value_lower = safe_text(
            value
        ).lower()

        if (
            query_lower
            and value_lower
            and query_lower in value_lower
        ):
            score += 30

    # =================================================
    # PATTERNS
    # =================================================

    patterns = safe_list(
        memory.get(
            "patterns",
            []
        )
    )

    score += (
        len(patterns) * 10
    )

    for pattern in patterns:

        pattern_lower = safe_text(
            pattern
        ).lower()

        if (
            query_lower
            and pattern_lower
            and query_lower in pattern_lower
        ):
            score += 35

    # =================================================
    # CONTENT FALLBACK
    # =================================================

    if (
        query_lower
        and content_lower
        and query_lower in content_lower
    ):
        score += 25

    return score


# =====================================================
# MEMORY LOADER WITH PAGINATION
# =====================================================

def load_table_memories(
    table_name,
    batch_size=1000
):

    table_memories = []
    offset = 0

    while True:

        response = (
            supabase
            .table(table_name)
            .select("*")
            .range(
                offset,
                offset + batch_size - 1
            )
            .execute()
        )

        batch = response.data or []

        if not batch:
            break

        table_memories.extend(
            batch
        )

        if len(batch) < batch_size:
            break

        offset += batch_size

    return table_memories


def load_all_memories():

    memories = []

    for table_name in TABLES:

        try:

            table_memories = load_table_memories(
                table_name
            )

            print(
                f"{table_name}: "
                f"{len(table_memories)}"
            )

            for memory in table_memories:

                memory["_table"] = table_name

                memories.append(
                    memory
                )

        except Exception as e:

            print(
                f"{table_name}: FAILED"
            )

            print(
                e
            )

    return memories


# =====================================================
# PACKET BUILDER
# =====================================================

def build_recall_packet(
    query,
    limit=25
):

    memories = load_all_memories()

    packet = []

    for memory in memories:

        score = calculate_memory_score(
            memory,
            query
        )

        if score <= 0:
            continue

        memory["_score"] = score

        packet.append(
            memory
        )

    packet.sort(
        key=lambda x: x.get(
            "_score",
            0
        ),
        reverse=True
    )

    return packet[:limit]


def format_recall_packet(
    query,
    limit=25
):

    packet = build_recall_packet(
        query,
        limit
    )

    lines = []

    lines.append(
        "RHEE RECALL PACKET"
    )

    lines.append(
        f"QUERY: {query}"
    )

    lines.append(
        f"MEMORIES FOUND: {len(packet)}"
    )

    lines.append(
        ""
    )

    for memory in packet:

        lines.append(
            f"{memory.get('_score')} | "
            f"{memory.get('_table')} | "
            f"{memory.get('primary_subject')}"
        )

        content = safe_text(
            memory.get(
                "content",
                ""
            )
        )

        if content:
            lines.append(
                content[:300]
            )

        lines.append(
            ""
        )

    return "\n".join(
        lines
    )


# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    print()
    print("=" * 50)
    print("RHEE V2 ONLINE")
    print("=" * 50)

    memories = load_all_memories()

    print()
    print(
        f"TOTAL MEMORIES LOADED: {len(memories)}"
    )

    print()
    print("=" * 50)
    print("RHEE TEST QUERY")
    print("=" * 50)

    print(
        format_recall_packet(
            "Luella",
            limit=10
        )
    )