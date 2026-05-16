# ============================================================
# MEMORY ORCHESTRATOR
# Operation Mnemosyne
# Central memory access point
# ============================================================

from memory.runtime.bridge import (
    process,
    build_context,
    runtime_status,
)

from memory.retrieval.bridge import (
    search_local_memory,
    build_retrieval_context,
    retrieval_status,
)

from memory.confidence.bridge import (
    calculate_basic_confidence,
    build_memory_confidence_layer,
    confidence_status,
)

from memory.patterns.bridge import (
    load_memory_patterns,
    load_memory_outcomes,
    pattern_status,
)

try:
    from memory.learning.bridge import learning_status
except Exception:
    def learning_status():
        return {
            "status": "degraded",
            "source": "memory.learning.bridge"
        }


def build_full_memory_context(user_msg):

    base_context = build_context()

    retrieved_context = build_retrieval_context(
        user_msg,
        limit=10
    )

    return (
        str(base_context or "")
        + "\n\n"
        + str(retrieved_context or "")
    ).strip()


def build_memory_runtime_package(user_msg):

    results = search_local_memory(
        user_msg,
        limit=10
    )

    confidence = calculate_basic_confidence(
        results
    )

    return {
        "context": build_full_memory_context(user_msg),
        "retrieval_results": results,
        "confidence": confidence,
        "confidence_layer": build_memory_confidence_layer(confidence),
        "status": memory_orchestration_status()
    }


def memory_orchestration_status():

    return {
        "status": "online",
        "operation": "AODS51",
        "runtime": runtime_status(),
        "retrieval": retrieval_status(),
        "confidence": confidence_status(),
        "patterns": pattern_status(),
        "learning": learning_status(),
        "source_of_truth": "memory/",
        "legacy_core_memory": "preserved_not_deleted"
    }
