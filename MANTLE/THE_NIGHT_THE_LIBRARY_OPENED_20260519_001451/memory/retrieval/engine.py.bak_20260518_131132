
# ============================================================
# SEMANTIC MEMORY DOMAINS
# ============================================================

SEMANTIC_DOMAINS = {

    "family": [
        "children",
        "kids",
        "daughter",
        "son",
        "iyla",
        "ashton",
        "luella",
        "mehlia"
    ],

    "project l": [
        "orchestration",
        "memory",
        "runtime",
        "captains",
        "tegan",
        "continuity",
        "supabase",
        "architecture"
    ],

    "hockey": [
        "sport",
        "field hockey",
        "fullback",
        "masters",
        "brisbane"
    ],

    "identity": [
        "values",
        "truth",
        "continuity",
        "growth",
        "modular"
    ]
}


# ============================================================
# MEMORY RETRIEVAL ENGINE
# Operation Mnemosyne + Retrieval Lieutenant
# ============================================================

from pathlib import Path
import json

from orchestration.lieutenants.retrieval_lieutenant import (
    RETRIEVAL_LIEUTENANT,
)

ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

PATTERNS_FILE = (
    ROOT
    / "memory"
    / "patterns"
    / "memory_patterns.json"
)


# ============================================================
# LOAD MEMORY PATTERNS
# ============================================================

def load_patterns():

    try:

        if not PATTERNS_FILE.exists():
            return []

        data = json.loads(
            PATTERNS_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, list):
            return data

        return []

    except Exception as e:

        print(
            "RETRIEVAL LOAD ERROR:",
            e
        )

        return []


# ============================================================
# SIMPLE RETRIEVAL
# ============================================================

def retrieve_memories(
    query,
    limit=10
):

    patterns = load_patterns()

    query_lower = str(query).lower()

    expanded_terms = set()

    for domain, terms in SEMANTIC_DOMAINS.items():

        if domain in query_lower:

            expanded_terms.update(terms)

        for term in terms:

            if term in query_lower:

                expanded_terms.update(terms)

                expanded_terms.add(domain)

    expanded_terms.update(
        query_lower.split()
    )

    results = []

    for entry in patterns:

        try:

            text = json.dumps(
                entry,
                ensure_ascii=False
            ).lower()

            score = 0

            for word in expanded_terms:

                if word in text:
                    score += 1

            if score > 0:

                results.append({

                    "_score": score,

                    "entry": entry
                })

        except Exception as e:

            print(
                "RETRIEVAL ENTRY ERROR:",
                e
            )

    results.sort(
        key=lambda x: x.get(
            "_score",
            0
        ),
        reverse=True
    )

    results = results[:limit]

    results = (
        RETRIEVAL_LIEUTENANT
        .process_retrieval(results)
    )

    return results


# ============================================================
# STATUS
# ============================================================

def retrieval_status():

    return {

        "status": "online",

        "source": "memory/retrieval",

        "operation": "AODS61"
    }

# ============================================================
# LEGACY COMPATIBILITY FUNCTIONS
# ============================================================

def collect_captain_memory_entries(
    captain_name=None,
    limit=25
):

    query = ""

    if captain_name:
        query = captain_name

    return retrieve_memories(
        query=query,
        limit=limit
    )

def search_local_memory(
    query,
    limit=10
):

    return retrieve_memories(
        query=query,
        limit=limit
    )


def build_retrieval_context(
    query,
    limit=10
):

    results = retrieve_memories(
        query=query,
        limit=limit
    )

    context_lines = []

    for item in results:

        try:

            entry = item.get(
                "entry",
                {}
            )

            category = str(
                entry.get(
                    "category",
                    "memory"
                )
            ).strip()

            content = str(
                entry.get(
                    "content",
                    ""
                )
            ).strip()

            if not content:
                continue

            line = f"[{category}] {content}"

            context_lines.append(line)

        except Exception as e:

            print(
                "MEMORY CONTEXT FORMAT ERROR:",
                e
            )

    if not context_lines:

        return (
            "No relevant memory context found."
        )

    return "\n".join(context_lines)





