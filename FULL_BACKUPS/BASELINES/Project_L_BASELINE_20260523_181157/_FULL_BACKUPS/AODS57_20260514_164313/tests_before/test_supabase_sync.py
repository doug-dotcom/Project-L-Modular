import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory.supabase_sync.sync_engine import (
    build_sync_manifest,
    export_sync_snapshot,
)

print("")
print("SUPABASE SYNC TEST")
print("")

manifest = build_sync_manifest()

print(manifest)

print("")
print("EXPORTING SNAPSHOT...")
print("")

result = export_sync_snapshot()

print(result)
