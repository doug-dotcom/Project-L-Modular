import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

DOMAIN_DIR = ROOT / "memory" / "domains"

OUT_DIR = ROOT / "memory" / "dynamic_priority"
REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"

PRIORITY_PATTERNS = {

    "critical_runtime": {
        "patterns": [
            "project l",
            "memory",
            "cognition",
            "runtime",
            "continuity"
        ],
        "weight": 5
    },

    "identity_priority": {
        "patterns": [
            "identity",
            "mask",
            "meaning",
            "doug",
            "self worth"
        ],
        "weight": 4
    },

    "recovery_priority": {
        "patterns": [
            "recovery",
            "regulation",
            "meetings",
            "growth",
            "healing"
        ],
        "weight": 3
    },

    "stress_priority": {
        "patterns": [
            "fear",
            "money",
            "unsafe",
            "panic",
            "stress"
        ],
        "weight": 4
    },

    "family_priority": {
        "patterns": [
            "family",
            "kids",
            "father",
            "iyla",
            "ashton"
        ],
        "weight": 3
    }
}

def normalize(text):

    if text is None:
        return ""

    if isinstance(text, dict):
        text = json.dumps(text, ensure_ascii=False)

    elif isinstance(text, list):
        text = " ".join([str(x) for x in text])

    else:
        text = str(text)

    return re.sub(r"\s+", " ", text).strip().lower()

def load_memories():

    memories = []

    if not DOMAIN_DIR.exists():
        return memories

    for path in DOMAIN_DIR.glob("*.json"):

        try:

            data = json.loads(
                path.read_text(encoding="utf-8")
            )

            for m in data.get("memories", []):

                text = normalize(
                    m.get("content")
                )

                if len(text) < 40:
                    continue

                memories.append(text)

        except:
            pass

    return memories

def prioritize(memories):

    scored = []

    for memory in memories:

        total = 0
        matched = []

        for category, cfg in PRIORITY_PATTERNS.items():

            score = 0

            for p in cfg["patterns"]:

                if p in memory:
                    score += cfg["weight"]

            if score > 0:
                matched.append(category)

            total += score

        if total > 0:

            scored.append({
                "priority_score": total,
                "matched_categories": matched,
                "memory": memory[:500]
            })

    scored = sorted(
        scored,
        key=lambda x: x["priority_score"],
        reverse=True
    )

    return scored

def run():

    print("")
    print("Loading memories...")

    memories = load_memories()

    print(f"Memories loaded: {len(memories)}")

    print("")
    print("Calculating dynamic recall priorities...")

    prioritized = prioritize(memories)

    output = {
        "created_at": str(datetime.utcnow()),
        "top_runtime_memories": prioritized[:250]
    }

    out_path = OUT_DIR / "dynamic_runtime_priorities.json"

    out_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"dynamic_priority_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Dynamic prioritization complete.")
    print(f"Priorities written to: {out_path}")
    print(f"Report written to: {report_path}")

    print("")
    print("Priority Summary:")
    print(f" - Runtime memories ranked: {len(prioritized)}")
    print(f" - Top runtime memories exported: 250")
    print("")

if __name__ == "__main__":
    run()

