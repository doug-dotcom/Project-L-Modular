import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestration.active_registry import (
    register_active_captains
)

from orchestration.runtime_dispatch import (
    build_dispatch_report
)

from orchestration.captains.communications.captain_emily import (
    CaptainEmily
)

from orchestration.captains.intelligence.captain_millie import (
    CaptainMillie
)

def emily_should(msg):
    return "email" in msg.lower()

def emily_execute(msg):
    return {
        "reply": "Emily deployed."
    }

def millie_should(msg):
    return "memory" in msg.lower()

def millie_execute(msg):
    return {
        "reply": "Millie deployed."
    }

emily = CaptainEmily(
    emily_should,
    emily_execute
)

millie = CaptainMillie(
    millie_should,
    millie_execute
)

register_active_captains([
    emily,
    millie
])

print("")
print(build_dispatch_report(
    "check my email"
))

print("")
print(build_dispatch_report(
    "show memory"
))

print("")
print("DYNAMIC DISPATCH ONLINE")
