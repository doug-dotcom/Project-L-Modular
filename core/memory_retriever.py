import json

from pathlib import Path

# =====================================================
# ROOT
# =====================================================

ROOT = Path(__file__).resolve().parents[1]

DOMAIN_DIR = ROOT / "memory" / "domains"

MAX_MEMORY_COUNT = 15
MAX_MEMORY_CHARS = 500
MAX_CONTEXT_CHARS = 4000

# =====================================================
# LOAD JSON
# =====================================================

def load_json(path):

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

            if isinstance(data, list):
                return data

            return []

    except Exception as e:

        print(
            f"MEMORY LOAD ERROR: {path.name} | {e}"
        )

        return []

# =====================================================
# SEARCH MEMORIES
# =====================================================

def search_memories(user_message):

    query = str(
        user_message
    ).lower()

    query_words = [
        word.strip()
        for word in query.split()
        if len(word.strip()) >= 3
    ]

    results = []

    if not query_words:

        return []

    files = DOMAIN_DIR.glob("*.json")

    for file in files:

        memories = load_json(file)

        for memory in memories:

            if not isinstance(memory, dict):
                continue

            content = str(
                memory.get(
                    "content",
                    ""
                )
            ).lower()

            score = sum(
                1
                for word in query_words
                if word in content
            )

            if score <= 0:
                continue

            results.append({

                "domain":
                    file.stem,

                "content":
                    memory.get(
                        "content",
                        ""
                    ),

                "priority":
                    memory.get(
                        "priority",
                        5
                    ),

                "salience":
                    memory.get(
                        "salience",
                        "medium"
                    ),

                "anchor":
                    memory.get(
                        "anchor",
                        False
                    ),

                "score":
                    score

            })

    return sorted(
        results,
        key=lambda x: (
            x["score"],
            x["priority"]
        ),
        reverse=True
    )[:MAX_MEMORY_COUNT]

# =====================================================
# BUILD CONTEXT
# =====================================================

def retrieve_memory_context(user_message):

    memories = search_memories(
        user_message
    )

    if not memories:

        print("LONG TERM MEMORY COUNT: 0")
        print("LONG TERM CONTEXT SIZE: 0")

        return "No relevant memories found."

    context = [
        "Relevant Long-Term Memory Context:"
    ]

    total_chars = 0

    for memory in memories:

        content = str(
            memory.get(
                "content",
                ""
            )
        )[:MAX_MEMORY_CHARS]

        line = (
            f"[{memory['domain']}] "
            f"{content}"
        )

        if total_chars + len(line) > MAX_CONTEXT_CHARS:
            break

        context.append(line)

        total_chars += len(line)

    final_context = "\n".join(context)

    print(
        f"LONG TERM MEMORY COUNT: {len(memories)}"
    )

    print(
        f"LONG TERM CONTEXT SIZE: {len(final_context)}"
    )

    return final_context
