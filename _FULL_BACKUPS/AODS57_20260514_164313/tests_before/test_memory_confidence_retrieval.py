import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 50 CONFIDENCE + RETRIEVAL TEST")
print("")

from memory.confidence.engine import (
    calculate_basic_confidence,
    build_memory_confidence_layer,
    confidence_status
)

from memory.retrieval.engine import (
    search_local_memory,
    build_retrieval_context,
    retrieval_status
)

sample = [
    {"_score": 9, "content": "test memory"}
]

print("confidence:", calculate_basic_confidence(sample))
print("confidence layer type:", type(build_memory_confidence_layer(calculate_basic_confidence(sample))).__name__)
print("confidence status:", confidence_status())

results = search_local_memory("Doug memory", limit=5)

print("retrieval results:", len(results))
print("retrieval context type:", type(build_retrieval_context("Doug memory", limit=5)).__name__)
print("retrieval status:", retrieval_status())

print("")
print("AODS 50 CONFIDENCE + RETRIEVAL ONLINE")
