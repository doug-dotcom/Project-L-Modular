# ============================================================
# MEMORY PATTERNS BRIDGE
# Compatibility bridge for existing core memory pattern files.
# No live cutover yet.
# ============================================================

from pathlib import Path
import json

ROOT = Path(r"C:\Shine_L")
CORE_PATTERNS = ROOT / "core" / "memory_patterns.json"
CORE_OUTCOMES = ROOT / "core" / "memory_outcomes.json"

def load_json(path, fallback):
    try:
        if not path.exists():
            return fallback
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print("PATTERNS BRIDGE LOAD ERROR:", e)
        return fallback

def load_memory_patterns():
    return load_json(CORE_PATTERNS, {})

def load_memory_outcomes():
    return load_json(CORE_OUTCOMES, {})

