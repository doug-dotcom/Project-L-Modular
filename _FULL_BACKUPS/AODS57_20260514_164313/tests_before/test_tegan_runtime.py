import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestration.active_registry import (
    register_active_captains
)

from orchestration.tegan_runtime import (
    MajorTeganRuntime
)

from orchestration.captains.communications.captain_emily import (
    CaptainEmily
)

def emily_should(msg):
    return "email" in msg.lower()

def emily_execute(msg):
    return {
        "reply": "Emily deployed."
    }

emily = CaptainEmily(
    emily_should,
    emily_execute
)

register_active_captains([
    emily
])

runtime = MajorTeganRuntime()

print("")
print(runtime.build_runtime_report(
    "check my email urgently"
))

print("")
print("TEGAN RUNTIME ONLINE")
