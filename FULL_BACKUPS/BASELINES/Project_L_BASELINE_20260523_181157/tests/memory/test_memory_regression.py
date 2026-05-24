import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 60 MEMORY REGRESSION TEST")
print("")

# ============================================================
# IMPORTS
# ============================================================

from memory.orchestrator import (
    build_memory_runtime_package,
    build_full_memory_context,
    memory_orchestration_status,
)

from memory.retrieval.engine import (
    search_local_memory,
    build_retrieval_context,
)

from memory.confidence.engine import (
    calculate_basic_confidence,
    build_memory_confidence_layer,
)

from memory.patterns.store import (
    load_memory_patterns,
    load_memory_outcomes,
)

# ============================================================
# MEMORY STATUS
# ============================================================

status = memory_orchestration_status()

if status.get("status") != "online":
    raise SystemExit(
        "Memory orchestrator offline"
    )

print("MEMORY ORCHESTRATOR: OK")

# ============================================================
# PATTERN LOAD
# ============================================================

patterns = load_memory_patterns()
outcomes = load_memory_outcomes()

if not isinstance(patterns, dict):
    raise SystemExit(
        "Patterns not dict"
    )

if not isinstance(outcomes, dict):
    raise SystemExit(
        "Outcomes not dict"
    )

print("PATTERN STORE: OK")

# ============================================================
# RETRIEVAL TEST
# ============================================================

results = search_local_memory(
    "Doug Shine memory",
    limit=5
)

if not isinstance(results, list):
    raise SystemExit(
        "Retrieval results not list"
    )

print("RETRIEVAL ENGINE: OK")

# ============================================================
# CONTEXT BUILD
# ============================================================

context = build_retrieval_context(
    "Doug Shine memory",
    limit=5
)

if not isinstance(context, str):
    raise SystemExit(
        "Retrieval context not string"
    )

full_context = build_full_memory_context(
    "Doug Shine memory"
)

if not isinstance(full_context, str):
    raise SystemExit(
        "Full memory context not string"
    )

print("CONTEXT BUILDING: OK")

# ============================================================
# CONFIDENCE TEST
# ============================================================

sample_matches = [
    {"_score": 9}
]

confidence = calculate_basic_confidence(
    sample_matches
)

if "confidence" not in confidence:
    raise SystemExit(
        "Confidence result invalid"
    )

layer = build_memory_confidence_layer(
    confidence
)

if not isinstance(layer, str):
    raise SystemExit(
        "Confidence layer not string"
    )

print("CONFIDENCE ENGINE: OK")

# ============================================================
# RUNTIME PACKAGE
# ============================================================

package = build_memory_runtime_package(
    "Doug Shine memory"
)

required = [
    "context",
    "retrieval_results",
    "confidence",
    "confidence_layer",
    "status",
]

missing = [
    k for k in required
    if k not in package
]

if missing:
    raise SystemExit(
        f"Runtime package missing: {missing}"
    )

print("MEMORY RUNTIME PACKAGE: OK")

# ============================================================
# REGRESSION CHECKS
# ============================================================

if status.get("source_of_truth") != "memory/":
    raise SystemExit(
        "Memory source_of_truth drift detected"
    )

if status.get("legacy_core_memory") != "preserved_not_deleted":
    raise SystemExit(
        "Legacy core memory status drift detected"
    )

print("REGRESSION CHECKS: OK")

print("")
print("AODS 60 MEMORY REGRESSION PASSED")
