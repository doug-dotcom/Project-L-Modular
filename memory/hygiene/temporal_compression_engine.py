import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

DOMAIN_DIR = ROOT / "memory" / "domains"
OUT_DIR = ROOT / "memory" / "temporal_clusters"
REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"

TIME_PATTERNS = {

    "may_2026_recovery_breakthrough": [
        "mask",
        "pauline",
        "if/when",
        "emotional exhaustion",
        "meetings",
        "recovery"
    ],

    "project_l_cognition_phase": [
        "project l",
        "semantic",
        "cognition",
        "memory",
        "vector",
        "active cognition"
    ],

    "relationship_transition_phase": [
        "leah",
        "abandonment",
        "wanted",
        "safety net",
        "alone"
    ],

    "identity_integration_phase": [
        "dougie",
        "douglas",
        "identity",
        "armor",
        "self-worth"
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

def detect_period(text):

    lowered = text.lower()

    scores = defaultdict(int)

    for phase, patterns in TIME_PATTERNS.items():
        for p in patterns:
            if p.lower() in lowered:
                scores[phase] += 1

    if not scores:
        return "general_background"

    return max(scores, key=scores.get)

def load_memories():

    items = []

    if not DOMAIN_DIR.exists():
        return items

    for path in DOMAIN_DIR.glob("*.json"):

        try:
            data = json.loads(path.read_text(encoding="utf-8"))

            for m in data.get("memories", []):

                content = normalize(m.get("content"))

                items.append({
                    "source": path.name,
                    "content": content
                })

        except:
            pass

    return items

def summarize(memories):

    phrases = []

    for m in memories[:15]:

        text = m["content"]

        if len(text) > 220:
            text = text[:220]

        phrases.append(text)

    return phrases

def run():

    print("")
    print("Loading memories...")

    memories = load_memories()

    print(f"Memories loaded: {len(memories)}")

    periods = defaultdict(list)

    for m in memories:

        phase = detect_period(m["content"])

        periods[phase].append(m)

    report = {
        "created_at": str(datetime.utcnow()),
        "total_memories": len(memories),
        "temporal_clusters": {}
    }

    for phase, items in periods.items():

        export = {
            "phase": phase,
            "memory_count": len(items),
            "summary": summarize(items),
            "memories": items[:500]
        }

        outpath = OUT_DIR / f"{phase}.json"

        outpath.write_text(
            json.dumps(export, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        report["temporal_clusters"][phase] = len(items)

    report_path = REPORT_DIR / f"temporal_compression_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Temporal compression complete.")
    print(f"Report written to: {report_path}")
    print("")
    print("Summary:")

    for k,v in sorted(report["temporal_clusters"].items(), key=lambda x: x[1], reverse=True):
        print(f"  {k}: {v}")

    print("")

if __name__ == "__main__":
    run()

