import json

from pathlib import Path
from datetime import datetime

from carol_cleaner import run_carol
from sally_salience import run_sally

# =====================================================
# ROOT
# =====================================================

ROOT = Path(__file__).resolve().parents[2]

DOMAIN_DIR = ROOT / "memory" / "domains"

DRY_RUN = False

# =====================================================
# LOG
# =====================================================

def log(msg):

    print(
        f"{datetime.now().isoformat()} | {msg}"
    )

# =====================================================
# LOAD JSON
# =====================================================

def load_json(path):

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

            if isinstance(data, list):
                return data

            return []

    except Exception as e:

        log(
            f"LOAD ERROR {path.name}: {e}"
        )

        return []

# =====================================================
# SAVE JSON
# =====================================================

def save_json(path, data):

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )

# =====================================================
# NORMALIZE MEMORY
# =====================================================

def normalize_memory(memory):

    if not isinstance(memory, dict):
        return None

    memory.setdefault("id", "unknown")

    memory.setdefault("role", "unknown")

    memory.setdefault("content", "")

    memory.setdefault(
        "created_at",
        datetime.now().isoformat()
    )

    return memory

# =====================================================
# PROCESS FILE
# =====================================================

def process_file(path):

    log(f"PROCESSING {path.name}")

    memories = load_json(path)

    before = len(memories)

    normalized = []

    # =============================================
    # NORMALIZE ALL LEGACY MEMORIES
    # =============================================

    for memory in memories:

        fixed = normalize_memory(memory)

        if fixed:
            normalized.append(fixed)

    # =============================================
    # CAROL CLEANER
    # =============================================

    cleaned = run_carol(normalized)

    # =============================================
    # SALLY SALIENCE
    # =============================================

    enriched = run_sally(cleaned)

    after = len(enriched)

    if not DRY_RUN:

        save_json(path, enriched)

    # =============================================
    # REPORT
    # =============================================

    anchors = sum(
        1 for m in enriched
        if m.get("anchor") == True
    )

    high_priority = sum(
        1 for m in enriched
        if m.get("priority", 0) >= 8
    )

    log(
        f"{path.name} | "
        f"{before} -> {after} | "
        f"anchors={anchors} | "
        f"high_priority={high_priority}"
    )

# =====================================================
# MAIN
# =====================================================

def run_master():

    files = sorted(
        DOMAIN_DIR.glob("*.json")
    )

    total = 0

    for file in files:

        process_file(file)

        total += 1

    log(
        f"FULL HYGIENE COMPLETE | "
        f"domains={total}"
    )

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":

    run_master()
