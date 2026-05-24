import json

from pathlib import Path

# =====================================================
# CLEAN MEMORY
# =====================================================

def clean_memory(memory):

    if not isinstance(memory, dict):
        return None

    memory.setdefault("cleaned", True)

    memory.setdefault("canonical", True)

    memory.setdefault("domain_verified", True)

    return memory

# =====================================================
# REMOVE DUPES
# =====================================================

def dedupe_memories(memories):

    seen = set()

    cleaned = []

    for memory in memories:

        memory_id = str(
            memory.get("id", "")
        )

        if not memory_id:
            continue

        if memory_id in seen:
            continue

        seen.add(memory_id)

        cleaned.append(memory)

    return cleaned

# =====================================================
# RUN CAROL
# =====================================================

def run_carol(memories):

    output = []

    for memory in memories:

        cleaned = clean_memory(memory)

        if cleaned:
            output.append(cleaned)

    output = dedupe_memories(output)

    return output
