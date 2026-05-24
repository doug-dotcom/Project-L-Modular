import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 64 SUPPRESSION LIEUTENANT TEST")
print("")

from orchestration.lieutenants.suppression_lieutenant import (
    SUPPRESSION_LIEUTENANT
)

meta = (
    SUPPRESSION_LIEUTENANT
    .should_suppress(
        "Explain the runtime architecture"
    )
)

low = (
    SUPPRESSION_LIEUTENANT
    .should_suppress(
        "😂"
    )
)

normal = (
    SUPPRESSION_LIEUTENANT
    .should_suppress(
        "check my email"
    )
)

if not meta["suppress"]:
    raise SystemExit("Meta suppression failed")

if not low["suppress"]:
    raise SystemExit("Low priority suppression failed")

if normal["suppress"]:
    raise SystemExit("Normal request incorrectly suppressed")

print("meta:", meta)
print("low:", low)
print("normal:", normal)

status = (
    SUPPRESSION_LIEUTENANT
    .runtime_status()
)

print("status:", status)

print("")
print("AODS 64 SUPPRESSION LIEUTENANT ONLINE")
