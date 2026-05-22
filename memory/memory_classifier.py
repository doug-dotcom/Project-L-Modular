import json
from pathlib import Path
from datetime import datetime

# ============================================================
# ROOT
# ============================================================

ROOT = Path(__file__).resolve().parents[1]

QUEUE_FILE = (
    ROOT
    / "memory"
    / "pending"
    / "pending_memory_queue.json"
)

# ============================================================
# DOMAIN RULES
# ============================================================

DOMAIN_RULES = {

    "family": [
        "family",
        "children",
        "kids",
        "iyla",
        "ashton",
        "luella",
        "mehlia",
        "daughter",
        "son"
    ],

    "identity": [
        "i am",
        "my name",
        "identity",
        "values",
        "who i am"
    ],

    "work": [
        "work",
        "tpd",
        "insurance",
        "claim",
        "anz",
        "career",
        "zurich"
    ],

    "health": [
        "health",
        "adhd",
        "ptsd",
        "doctor",
        "therapy",
        "psychologist",
        "mental"
    ],

    "sport": [
        "hockey",
        "sport",
        "masters",
        "fullback",
        "netball"
    ],

    "project_l": [
        "project l",
        "memory",
        "aods",
        "orchestration",
        "cognition",
        "tegan",
        "emily",
        "callie",
        "tania"
    ],

    "emotional": [
        "feel",
        "emotion",
        "angry",
        "sad",
        "excited",
        "flat",
        "joy",
        "trigger"
    ]
}

# ============================================================
# LOAD QUEUE
# ============================================================

def load_queue():

    try:

        if not QUEUE_FILE.exists():
            return []

        return json.loads(

            QUEUE_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception as e:

        print(f"LOAD ERROR: {e}")

        return []

# ============================================================
# SAVE QUEUE
# ============================================================

def save_queue(queue):

    QUEUE_FILE.write_text(

        json.dumps(
            queue,
            indent=2,
            ensure_ascii=False
        ),

        encoding="utf-8"
    )

# ============================================================
# CLASSIFIER
# ============================================================

def classify_text(text):

    text_lower = str(text).lower()

    best_domain = "general"

    best_score = 0

    for domain, keywords in DOMAIN_RULES.items():

        score = 0

        for keyword in keywords:

            if keyword in text_lower:
                score += 1

        if score > best_score:

            best_score = score

            best_domain = domain

    return best_domain

# ============================================================
# CLASSIFY PENDING QUEUE
# ============================================================

def classify_pending_queue():

    queue = load_queue()

    updated = 0

    for item in queue:

        # ====================================================
        # SKIP ALREADY CLASSIFIED
        # ====================================================

        if item.get("status") == "classified":
            continue

        content = item.get(
            "content",
            ""
        )

        # ====================================================
        # CLASSIFY
        # ====================================================

        domain = classify_text(content)

        item["proposed_domain"] = domain

        item["classified_at"] = str(
            datetime.now()
        )

        item["status"] = "classified"

        updated += 1

    # ========================================================
    # SAVE UPDATED QUEUE
    # ========================================================

    save_queue(queue)

    return {

        "status": "ok",

        "classified": updated,

        "queue_size": len(queue)
    }

# ============================================================
# STATUS
# ============================================================

def classifier_status():

    queue = load_queue()

    counts = {}

    for item in queue:

        domain = item.get(
            "proposed_domain",
            "unclassified"
        )

        counts[domain] = (
            counts.get(domain, 0) + 1
        )

    return {

        "status": "online",

        "queue_size": len(queue),

        "domains": counts
    }

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    result = classify_pending_queue()

    print(
        json.dumps(
            result,
            indent=2
        )
    )