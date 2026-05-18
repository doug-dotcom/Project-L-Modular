# =========================================================
# PROJECT L — UNIFIED MEMORY ENGINE
# =========================================================

import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MEMORY_DIR = os.path.join(BASE_DIR, "memory")

IDENTITY_FILE   = os.path.join(MEMORY_DIR, "identity.json")
EPISODIC_FILE   = os.path.join(MEMORY_DIR, "episodic.json")
EMOTIONAL_FILE  = os.path.join(MEMORY_DIR, "emotional.json")
STRUCTURED_FILE = os.path.join(MEMORY_DIR, "structured.json")
SESSION_FILE    = os.path.join(MEMORY_DIR, "session.json")

# =========================================================
# SAFE LOAD
# =========================================================

def safe_load(path, default):

    try:

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:

        print(f"[LOAD ERROR] {path}: {e}")

        return default

# =========================================================
# SAFE SAVE
# =========================================================

def safe_save(path, data):

    try:

        with open(path, "w", encoding="utf-8") as f:

            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False
            )

        return True

    except Exception as e:

        print(f"[SAVE ERROR] {path}: {e}")

        return False

# =========================================================
# LOAD ALL MEMORY
# =========================================================

def load_all_memory():

    return {
        "identity": safe_load(IDENTITY_FILE, {}),
        "episodic": safe_load(EPISODIC_FILE, []),
        "emotional": safe_load(EMOTIONAL_FILE, []),
        "structured": safe_load(STRUCTURED_FILE, []),
        "session": safe_load(SESSION_FILE, [])
    }

# =========================================================
# SAVE MEMORY
# =========================================================

def save_memory(memory_type, content):

    timestamp = datetime.now().isoformat()

    entry = {
        "timestamp": timestamp,
        "content": content
    }

    # -----------------------------------------------------
    # IDENTITY
    # -----------------------------------------------------

    if memory_type == "identity":

        existing = safe_load(IDENTITY_FILE, {})

        if isinstance(content, dict):
            existing.update(content)

        safe_save(IDENTITY_FILE, existing)

        return True

    # -----------------------------------------------------
    # OTHER MEMORY TYPES
    # -----------------------------------------------------

    mapping = {
        "episodic": EPISODIC_FILE,
        "emotional": EMOTIONAL_FILE,
        "structured": STRUCTURED_FILE,
        "session": SESSION_FILE
    }

    if memory_type not in mapping:
        return False

    path = mapping[memory_type]

    existing = safe_load(path, [])

    existing.append(entry)

    existing = existing[-5000:]

    safe_save(path, existing)

    return True

# =========================================================
# RECENT MEMORY CONTEXT
# =========================================================

def build_memory_context(limit=15):

    memory = load_all_memory()

    output = []

    # -----------------------------------------------------
    # IDENTITY
    # -----------------------------------------------------

    identity = memory.get("identity", {})

    if identity:

        output.append("=== IDENTITY ===")

        for k, v in identity.items():

            output.append(f"{k}: {v}")

    # -----------------------------------------------------
    # COMBINED MEMORIES
    # -----------------------------------------------------

    combined = []

    for mem_type in [
        "episodic",
        "emotional",
        "structured",
        "session"
    ]:

        for item in memory.get(mem_type, []):

            item["memory_type"] = mem_type

            combined.append(item)

    combined.sort(
        key=lambda x: x.get("timestamp", ""),
        reverse=True
    )

    output.append("")
    output.append("=== RECENT MEMORIES ===")

    for item in combined[:limit]:

        output.append(
            f"[{item['memory_type'].upper()}] {item['content']}"
        )

    return "\n".join(output)

# =========================================================
# MEMORY STATS
# =========================================================

def memory_stats():

    m = load_all_memory()

    return {
        "identity": len(m["identity"]),
        "episodic": len(m["episodic"]),
        "emotional": len(m["emotional"]),
        "structured": len(m["structured"]),
        "session": len(m["session"])
    }

# =========================================================
# TEST
# =========================================================

if __name__ == "__main__":

    print("")
    print("===================================")
    print("PROJECT L MEMORY ENGINE")
    print("===================================")
    print("")

    print(memory_stats())

    print("")
    print("Memory engine ready.")
    print("")
