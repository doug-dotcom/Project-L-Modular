# ============================================================
# MEMORY QUEUE ENGINE
# AODS-105
# ============================================================

import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]

QUEUE_FILE = (
    ROOT
    / "memory"
    / "pending"
    / "pending_memory_queue.json"
)

# ============================================================
# LOAD QUEUE
# ============================================================

def load_memory_queue():

    try:

        if not QUEUE_FILE.exists():
            return []

        return json.loads(

            QUEUE_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        return []

# ============================================================
# SAVE QUEUE
# ============================================================

def save_memory_queue(queue):

    QUEUE_FILE.write_text(

        json.dumps(
            queue,
            indent=2,
            ensure_ascii=False
        ),

        encoding="utf-8"
    )

# ============================================================
# MEMORY CANDIDATE DETECTOR
# ============================================================

def should_queue_memory(text):

    text_lower = str(text).lower()

    triggers = [

        "remember",
        "please save",
        "important",
        "my daughter",
        "my son",
        "my kids",
        "my family",
        "project l",
        "i am",
        "i have",
        "i feel",
        "my appointment",
        "my doctor",
        "my psychologist",
        "my goal",
        "my work",
        "my tpd"
    ]

    for trigger in triggers:

        if trigger in text_lower:
            return True

    return False

# ============================================================
# IMPORTANCE SCORE
# ============================================================

def calculate_importance(text):

    text_lower = str(text).lower()

    score = 3

    high_priority = [

        "project l",
        "children",
        "family",
        "important",
        "remember this",
        "please save",
        "tpd",
        "doctor",
        "psychologist",
        "goal"
    ]

    for item in high_priority:

        if item in text_lower:
            score += 2

    return min(score, 10)

# ============================================================
# QUEUE MEMORY
# ============================================================

def queue_memory_candidate(user_message):

    try:

        if not should_queue_memory(user_message):
            return False

        queue = load_memory_queue()

        entry = {

            "timestamp": str(
                datetime.now()
            ),

            "content": str(
                user_message
            ),

            "importance": calculate_importance(
                user_message
            ),

            "status": "pending"
        }

        queue.append(entry)

        queue = queue[-500:]

        save_memory_queue(queue)

        return True

    except Exception as e:

        print(
            "QUEUE MEMORY ERROR:",
            e
        )

        return False
