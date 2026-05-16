import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestration.active_registry import (
    register_active_captains,
    get_active_captains,
    build_runtime_roster
)

from orchestration.captains.communications.captain_emily import (
    CaptainEmily
)

def should_handle(msg):
    return "email" in msg.lower()

def execute(msg):
    return {
        "reply": "Emily deployed."
    }

emily = CaptainEmily(
    should_handle,
    execute
)

register_active_captains([
    emily
])

print("")
print(build_runtime_roster())

print("")
print("ACTIVE CAPTAINS:")
print(get_active_captains())

print("")
print("ACTIVE REGISTRY ONLINE")
