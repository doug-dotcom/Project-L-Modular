# ============================================================
# MEMORY CONFIDENCE ENGINE
# Operation Mnemosyne + Lieutenant Systems
# ============================================================

from orchestration.lieutenants.confidence_lieutenant import (
    CONFIDENCE_LIEUTENANT,
)


def calculate_basic_confidence(matches):

    return CONFIDENCE_LIEUTENANT.assess_memory_confidence(
        matches
    )


def build_memory_confidence_layer(confidence_data):

    return CONFIDENCE_LIEUTENANT.build_confidence_prompt_layer(
        confidence_data
    )


def confidence_status():

    lieutenant = CONFIDENCE_LIEUTENANT.runtime_status()

    return {
        "status": "online",
        "source": "memory/confidence",
        "operation": "AODS62",
        "lieutenant": lieutenant
    }

