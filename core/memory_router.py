import json
import os
from pathlib import Path
from datetime import datetime

BASE = Path("memory")

MEMORY_FILES = {
    "structured": BASE / "structured.json",
    "reflections": BASE / "reflections.json",
    "episodes": BASE / "episodes.json",
    "identity": BASE / "identity.json",
    "scratchpad": BASE / "scratchpad.json"
}

def ensure_files():
    BASE.mkdir(exist_ok=True)

    for name, path in MEMORY_FILES.items():
        if not path.exists():
            with open(path, "w", encoding="utf-8") as f:
                json.dump([], f)

def load_memory(name):
    ensure_files()

    path = MEMORY_FILES.get(name)

    if not path:
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_memory(name, item):
    ensure_files()

    path = MEMORY_FILES.get(name)

    if not path:
        return False

    try:
        data = load_memory(name)

        item["timestamp"] = datetime.now().isoformat()

        data.append(item)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return True

    except Exception as e:
        print(f"[MEMORY ERROR] {e}")
        return False

def memory_summary():
    ensure_files()

    result = {}

    for name, path in MEMORY_FILES.items():
        try:
            with open(path, "r", encoding="utf-8") as f:
                result[name] = len(json.load(f))
        except:
            result[name] = 0

    return result
