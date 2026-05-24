import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("")
print("AODS 55 LEGACY COMPATIBILITY TEST")
print("")

from core.legacy_compatibility import (
    compatibility_status,
    build_legacy_runtime,
)

status = compatibility_status()

print("status:", status.get("status"))
print("phase:", status.get("phase"))
print("server role:", status.get("server_role"))

runtime = build_legacy_runtime()

print("runtime keys:", list(runtime.keys()))

print("")
print("LEGACY COMPATIBILITY ONLINE")
