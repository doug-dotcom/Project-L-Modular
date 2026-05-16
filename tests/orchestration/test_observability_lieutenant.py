import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 66 OBSERVABILITY LIEUTENANT TEST")
print("")

from orchestration.lieutenants.observability_lieutenant import (
    OBSERVABILITY_LIEUTENANT
)

OBSERVABILITY_LIEUTENANT.record_event(
    "test_event",
    {
        "captain": "Emily",
        "handled": True,
        "message": "check my email"
    }
)

snapshot = (
    OBSERVABILITY_LIEUTENANT
    .build_runtime_snapshot()
)

if "total_events" not in snapshot:
    raise SystemExit(
        "Snapshot invalid"
    )

status = (
    OBSERVABILITY_LIEUTENANT
    .runtime_status()
)

print("snapshot:", snapshot)
print("status:", status)

print("")
print("AODS 66 OBSERVABILITY LIEUTENANT ONLINE")
