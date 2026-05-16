import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 65 CONTINUITY LIEUTENANT TEST")
print("")

from orchestration.lieutenants.continuity_lieutenant import (
    CONTINUITY_LIEUTENANT
)

state = (
    CONTINUITY_LIEUTENANT
    .update_context(
        "Doug wants to discuss Shine architecture and memory",
        {
            "captain": "Millie"
        }
    )
)

if "topics" not in state:
    raise SystemExit(
        "Topics missing"
    )

layer = (
    CONTINUITY_LIEUTENANT
    .build_continuity_layer()
)

if not isinstance(layer, str):
    raise SystemExit(
        "Continuity layer invalid"
    )

status = (
    CONTINUITY_LIEUTENANT
    .runtime_status()
)

print("state:", state)
print("layer:", layer)
print("status:", status)

print("")
print("AODS 65 CONTINUITY LIEUTENANT ONLINE")
