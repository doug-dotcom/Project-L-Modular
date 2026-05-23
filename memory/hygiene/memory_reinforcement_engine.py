import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

DOMAIN_DIR = ROOT / "memory" / "domains"
OUT_DIR = ROOT / "memory" / "reinforcement"
REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"

PATTERNS = {

    "mask_survival": [
        "mask",
        "survival",
        "protection",
        "armour",
        "armor"
    ],

    "identity_loop": [
        "identity",
        "who i am",
        "self worth",
        "meaning"
    ],

    "recovery_loop": [
        "recovery",
        "healing",
        "growth",
        "meetings",
        "step"
    ],

    "future_fear": [
        "future",
        "fear",
        "money",
        "stress",
        "uncertainty"
    ],

    "project_l_core": [
        "project l",
        "memory",
        "cognition",
        "ai",
        "shine"
    ]
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

                text = normalize(m.get("content"))

                if len(text) < 40:
                    continue

                memories.append(text)

        except:
            pass

    return memories

def analyze(memories):

    reinforcement = defaultdict(list)

    for memory in memories:

        for category, patterns in PATTERNS.items():

            score = 0

            for p in patterns:
                if p in memory:
                    score += 1

            if score > 0:

                reinforcement[category].append({
                    "strength": score,
                    "memory": memory[:400]
                })

    return reinforcement

def run():

    print("")
    print("Loading memories...")

    memories = load_memories()

    print(f"Memories loaded: {len(memories)}")

    results = analyze(memories)

    summary = {}

    for k, v in results.items():

        total_strength = sum(
            item["strength"] for item in v
        )

        summary[k] = {
            "memory_count": len(v),
            "reinforcement_strength": total_strength
        }

    out = {
        "created_at": str(datetime.utcnow()),
        "summary": summary,
        "reinforcement": results
    }

    out_path = OUT_DIR / "reinforcement_map.json"

    out_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"reinforcement_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Reinforcement engine complete.")
    print(f"Report written to: {report_path}")
    print("")
    print("Summary:")

    for k, v in summary.items():

        print(
            f"  {k}: "
            f"{v['memory_count']} memories | "
            f"strength {v['reinforcement_strength']}"
        )

    print("")

if __name__ == "__main__":
    run()

