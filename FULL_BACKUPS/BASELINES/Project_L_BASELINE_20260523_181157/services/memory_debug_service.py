# =====================================================
# memory_debug_service.py
# AODS 54
# =====================================================

from services.memory_context_service import (
    latest_memory,
    build_memory_context
)

def debug_memory_context():

    return {
        "structured": latest_memory("structured"),
        "reflections": latest_memory("reflections"),
        "scratchpad": latest_memory("scratchpad"),
        "combined_context": build_memory_context()
    }
