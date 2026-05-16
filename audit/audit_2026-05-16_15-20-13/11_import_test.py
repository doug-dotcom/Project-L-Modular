import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")
sys.path.insert(0, str(ROOT))

checks = [
    ("api.server", "app"),
    ("core.memory_engine", "memory_stats"),
]

for module_name, attr in checks:
    try:
        mod = __import__(module_name, fromlist=[attr])
        obj = getattr(mod, attr)
        print(f"PASS: {module_name}.{attr}")
    except Exception as e:
        print(f"FAIL: {module_name}.{attr} -> {e}")
