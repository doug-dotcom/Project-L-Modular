# ============================================================
# MEMORY PATTERN STORE
# Operation Mnemosyne
# ============================================================

import json
from pathlib import Path

ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

PATTERNS_FILE = ROOT / "memory" / "patterns" / "memory_patterns.json"
OUTCOMES_FILE = ROOT / "memory" / "patterns" / "memory_outcomes.json"


def load_json(path, fallback):

    try:
        if not path.exists():
            return fallback

        return json.loads(
            path.read_text(encoding="utf-8")
        )

    except Exception as e:
        print("MEMORY PATTERN LOAD ERROR:", e)
        return fallback


def save_json(path, data):

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


def load_memory_patterns():

    return load_json(
        PATTERNS_FILE,
        {}
    )


def load_memory_outcomes():

    return load_json(
        OUTCOMES_FILE,
        {}
    )


def save_memory_patterns(data):

    save_json(
        PATTERNS_FILE,
        data
    )


def save_memory_outcomes(data):

    save_json(
        OUTCOMES_FILE,
        data
    )


def pattern_status():

    patterns = load_memory_patterns()
    outcomes = load_memory_outcomes()

    return {
        "status": "online",
        "source": "memory/patterns",
        "patterns_type": type(patterns).__name__,
        "outcomes_type": type(outcomes).__name__
    }

