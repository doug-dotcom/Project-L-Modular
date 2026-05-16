import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 63 ROUTING LIEUTENANT TEST")
print("")

from orchestration.lieutenants.routing_lieutenant import (
    ROUTING_LIEUTENANT
)

from orchestration.active_registry import (
    register_active_captains
)

from orchestration.runtime_dispatch import (
    dynamic_dispatch
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

result = dynamic_dispatch(
    "check my email urgently"
)

if result["captain"] != "Emily":
    raise SystemExit(
        "Routing Lieutenant failed"
    )

print("dispatch:", result)

status = (
    ROUTING_LIEUTENANT
    .runtime_status()
)

print("status:", status)

print("")
print("AODS 63 ROUTING LIEUTENANT ONLINE")
