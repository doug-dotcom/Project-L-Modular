from memory.memory_engine import (
    build_context,
    save_structured_to_supabase,
    _load_supabase_facts
)

from datetime import datetime

# =====================================================
# ROUTING
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "millie",
        "memory keeper",
        "remember this",
        "save this memory",
        "preserve this",
        "what do you remember",
        "memory audit",
        "search memory",
        "recall"

    ]

    return any(
        t in text
        for t in triggers
    )

# =====================================================
# SAVE MEMORY
# =====================================================

def add_memory(message):

    clean = (
        message
        .replace("millie", "")
        .replace("remember this", "")
        .replace("save this memory", "")
        .strip()
    )

    if not clean:
        clean = message.strip()

    save_structured_to_supabase(clean)

    return clean

# =====================================================
# SEARCH MEMORY
# =====================================================

def search_memories(message):

    facts = _load_supabase_facts(100)

    text = message.lower()

    results = []

    for fact in facts:

        score = 0

        lower = fact.lower()

        for word in text.split():

            if len(word) > 3 and word in lower:

                score += 1

        if score > 0:

            results.append(
                (score, fact)
            )

    results.sort(
        reverse=True,
        key=lambda x: x[0]
    )

    return [x[1] for x in results[:8]]

# =====================================================
# MEMORY AUDIT
# =====================================================

def memory_audit():

    facts = _load_supabase_facts(500)

    return (
        "# Memory Audit\n\n"
        f"Total Supabase memories: {len(facts)}"
    )

# =====================================================
# MAIN HANDLER
# =====================================================

def handle_memory_request(message: str):

    text = message.lower()

    if "audit" in text:

        return memory_audit()

    if (
        "recall" in text
        or "search" in text
        or "remember" in text
        or "what do you remember" in text
    ):

        results = search_memories(message)

        if not results:

            return (
                "I could not find matching memories."
            )

        reply = "Matching memories:\n\n"

        for i, item in enumerate(results, start=1):

            reply += (
                f"{i}. {item}\n\n"
            )

        return reply

    saved = add_memory(message)

    return (
        "Memory saved:\n\n"
        + saved
    )
