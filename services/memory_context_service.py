# =====================================================
# memory_context_service.py
# AODS 54
# =====================================================

from core.memory_router import load_memory
from services.runtime_graph_ingest_service import ingest_memory_event

MAX_ITEMS = 5

def latest_memory(memory_type="structured", limit=MAX_ITEMS):

    try:
        memories = load_memory(memory_type)

        if not isinstance(memories, list):
            return []

        return memories[-limit:]

    except Exception:
        return []

def flatten_memory(memories):

    lines = []

    for item in memories:

        if isinstance(item, dict):

            if "text" in item:
                lines.append(str(item["text"]))

            elif "event" in item:
                lines.append(str(item["event"]))

            else:
                lines.append(str(item))

        else:
            lines.append(str(item))

    return "\n".join(lines)

def build_memory_context():

    structured = latest_memory("structured")
    reflections = latest_memory("reflections")
    scratchpad = latest_memory("scratchpad")

    combined = (
        structured +
        reflections +
        scratchpad
    )

    return flatten_memory(combined)

