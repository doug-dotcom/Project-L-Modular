import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

DOMAIN_DIR = ROOT / "memory" / "domains"
OUT_DIR = ROOT / "memory" / "hydration"
REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"

TRIGGERS = {

    "mask": [
        "identity",
        "survival",
        "protection",
        "pauline",
        "recovery"
    ],

    "project l": [
        "memory",
        "cognition",
        "shine",
        "ai",
        "meaning"
    ],

    "family": [
        "kids",
        "father",
        "love",
        "fear",
        "protection"
    ],

    "nervous system": [
        "trauma",
        "regulation",
        "stress",
        "recovery"
    ],

    "future": [
        "fear",
        "hope",
        "meaning",
        "project l"
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

    return re.sub(r"\s+", " ", text).strip()

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

def build_hydration(memories):

    graph = defaultdict(list)

    for memory in memories:

        lowered = memory.lower()

        for trigger, links in TRIGGERS.items():

            if trigger in lowered:

                for linked in links:

                    if linked in lowered:

                        graph[trigger].append({
                            "linked_to": linked,
                            "memory": memory[:500]
                        })

    return graph

def run():

    print("")
    print("Loading memories...")

    memories = load_memories()

    print(f"Memories loaded: {len(memories)}")

    graph = build_hydration(memories)

    out = {
        "created_at": str(datetime.utcnow()),
        "hydration_graph": graph
    }

    out_path = OUT_DIR / "hydration_graph.json"

    out_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"hydration_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Hydration engine complete.")
    print(f"Report written to: {report_path}")
    print("")

    print("Summary:")

    for k, v in graph.items():
        print(f"  {k}: {len(v)} links")

    print("")

if __name__ == "__main__":
    run()

