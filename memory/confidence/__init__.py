# ============================================================
# MEMORY CONFIDENCE EXPORTS
# ============================================================

from memory.confidence.engine import (
    calculate_basic_confidence,
    build_memory_confidence_layer,
    confidence_status,
)


def apply_memory_confidence(matches):

    return calculate_basic_confidence(matches)