import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 54 RUNTIME GLUE EXTRACTION TEST")
print("")

from orchestration.runtime_bootstrap import (
    build_runtime_stack,
    build_runtime_status,
)

stack = build_runtime_stack()

print("runtime stack keys:", list(stack.keys()))

status = build_runtime_status()

print("status:", status.get("status"))
print("phase:", status.get("phase"))
print("runtime_engine:", status.get("runtime_engine"))
print("tegan_runtime:", status.get("tegan_runtime"))

print("")
print("RUNTIME BOOTSTRAP ONLINE")
