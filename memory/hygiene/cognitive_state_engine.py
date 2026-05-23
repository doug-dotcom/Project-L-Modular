import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

DOMAIN_DIR = ROOT / "memory" / "domains"
OUT_DIR = ROOT / "memory" / "state"
REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"

STATES = {

    "safe_reflective": [
        "growth",
        "healing",
        "understanding",
        "reflection",
        "gratitude",
        "calm",
        "wisdom"
    ],

    "survival_stress": [
        "fear",
        "money",
        "panic",
        "stress",
        "survival",
        "pressure",
        "unsafe"
    ],

    "identity_processing": [
        "identity",
        "who i am",
        "mask",
        "self worth",
        "meaning",
        "doug",
        "dougie",
        "douglas"
    ],

    "project_execution": [
        "project l",
        "build",
        "memory",
        "ai",
        "engine",
        "architecture",
        "cognition"
    ],

    "recovery_regulation": [
        "recovery",
        "meetings",
        "step",
        "addiction",
        "nervous system",
        "regulation"
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

def classify(memories):

    state_map = defaultdict(list)

    for memory in memories:

        for state, patterns in STATES.items():

            score = 0

            for p in patterns:
                if p in memory:
                    score += 1

            if score > 0:

                state_map[state].append({
                    "score": score,
                    "memory": memory[:400]
                })

    return state_map

def run():

    print("")
    print("Loading memories...")

    memories = load_memories()

    print(f"Memories loaded: {len(memories)}")

    print("")
    print("Building cognitive states...")

    state_map = classify(memories)

    summary = {}

    for state, items in state_map.items():

        total = sum(x["score"] for x in items)

        summary[state] = {
            "memory_count": len(items),
            "activation_strength": total
        }

    output = {
        "created_at": str(datetime.utcnow()),
        "states": summary,
        "memory_state_map": state_map
    }

    out_path = OUT_DIR / "cognitive_states.json"

    out_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"cognitive_state_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Cognitive state engine complete.")
    print(f"Report written to: {report_path}")

    print("")
    print("Summary:")

    for k, v in summary.items():

        print(
            f"  {k}: "
            f"{v['memory_count']} memories | "
            f"activation {v['activation_strength']}"
        )

    print("")

if __name__ == "__main__":
    run()

