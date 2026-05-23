import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

DOMAIN_DIR = ROOT / "memory" / "domains"
STATE_FILE = ROOT / "memory" / "state" / "cognitive_states.json"

OUT_DIR = ROOT / "memory" / "attention"
REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"

ATTENTION_RULES = {

    "survival_attention": {
        "patterns": [
            "fear",
            "stress",
            "unsafe",
            "money",
            "panic"
        ],
        "weight": 3
    },

    "identity_attention": {
        "patterns": [
            "identity",
            "mask",
            "meaning",
            "self worth",
            "doug"
        ],
        "weight": 2
    },

    "project_attention": {
        "patterns": [
            "project l",
            "memory",
            "architecture",
            "cognition",
            "build"
        ],
        "weight": 4
    },

    "recovery_attention": {
        "patterns": [
            "recovery",
            "healing",
            "meetings",
            "regulation",
            "growth"
        ],
        "weight": 2
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

                text = normalize(m.get("content"))

                if len(text) < 40:
                    continue

                memories.append(text)

        except:
            pass

    return memories

def build_attention(memories):

    focus_map = defaultdict(list)

    for memory in memories:

        for focus_type, config in ATTENTION_RULES.items():

            score = 0

            for p in config["patterns"]:

                if p in memory:
                    score += config["weight"]

            if score > 0:

                focus_map[focus_type].append({
                    "attention_score": score,
                    "memory": memory[:400]
                })

    return focus_map

def run():

    print("")
    print("Loading memories...")

    memories = load_memories()

    print(f"Memories loaded: {len(memories)}")

    print("")
    print("Building attention orchestration...")

    focus_map = build_attention(memories)

    summary = {}

    for focus, items in focus_map.items():

        total_attention = sum(
            x["attention_score"] for x in items
        )

        summary[focus] = {
            "memory_count": len(items),
            "attention_strength": total_attention
        }

    output = {
        "created_at": str(datetime.utcnow()),
        "attention_summary": summary,
        "focus_map": focus_map
    }

    out_path = OUT_DIR / "attention_orchestration.json"

    out_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"attention_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Attention orchestration complete.")
    print(f"Report written to: {report_path}")

    print("")
    print("Summary:")

    for k, v in summary.items():

        print(
            f"  {k}: "
            f"{v['memory_count']} memories | "
            f"attention {v['attention_strength']}"
        )

    print("")

if __name__ == "__main__":
    run()

