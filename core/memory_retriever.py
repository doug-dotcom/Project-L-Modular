import json

from pathlib import Path

# =====================================================
# ROOT
# =====================================================

ROOT = Path(__file__).resolve().parents[1]

DOMAIN_DIR = ROOT / "memory" / "domains"

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

    except:

        return []

# =====================================================
# SEARCH MEMORIES
# =====================================================

def search_memories(user_message):

    query = str(user_message).lower()

    results = []

    files = DOMAIN_DIR.glob("*.json")

    for file in files:

        memories = load_json(file)

        for memory in memories:

            if not isinstance(memory, dict):
                continue

            content = str(
                memory.get("content", "")
            ).lower()

            if query in content:

                results.append({

                    "domain": file.stem,

                    "content": memory.get(
                        "content",
                        ""
                    ),

                    "priority": memory.get(
                        "priority",
                        5
                    ),

                    "salience": memory.get(
                        "salience",
                        "medium"
                    ),

                    "anchor": memory.get(
                        "anchor",
                        False
                    )
                })

    return sorted(
        results,
        key=lambda x: x["priority"],
        reverse=True
    )[:15]

# =====================================================
# BUILD CONTEXT
# =====================================================

def retrieve_memory_context(user_message):

    memories = search_memories(user_message)

    if not memories:

        return "No relevant memories found."

    context = []

    context.append(
        "Relevant Memory Context:"
    )

    for memory in memories:

        line = (
            f"[{memory['domain']}] "
            f"{memory['content']}"
        )

        context.append(line)

    return "\n".join(context)
