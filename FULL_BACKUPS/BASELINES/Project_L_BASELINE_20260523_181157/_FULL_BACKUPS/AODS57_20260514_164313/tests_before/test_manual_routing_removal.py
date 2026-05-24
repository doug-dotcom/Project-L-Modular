import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestration.tegan_runtime import (
    MajorTeganRuntime
)

print("")
print("MANUAL ROUTING REMOVAL TEST")
print("")

runtime = MajorTeganRuntime()

result = runtime.process(
    "check my email urgently"
)

print(result)

print("")
print("DYNAMIC DEPLOYMENT ACTIVE")
