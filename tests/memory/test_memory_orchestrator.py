import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 51 MEMORY ORCHESTRATION TEST")
print("")

from memory.orchestrator import (
    build_full_memory_context,
    build_memory_runtime_package,
    memory_orchestration_status,
)

status = memory_orchestration_status()

print("status:", status.get("status"))
print("source:", status.get("source_of_truth"))

package = build_memory_runtime_package(
    "Doug memory Shine"
)

print("package keys:", package.keys())
print("context type:", type(package.get("context")).__name__)
print("confidence:", package.get("confidence"))

context = build_full_memory_context(
    "Doug memory Shine"
)

print("context type:", type(context).__name__)
print("context length:", len(context))

print("")
print("AODS 51 MEMORY ORCHESTRATION ONLINE")
