import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

DOMAIN_DIR = ROOT / "memory" / "domains"
OUT_DIR = ROOT / "memory" / "priority"
REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"

PRIORITY_RULES = {

    "critical": [
        "suicide",
        "self harm",
        "not alive",
        "kids",
        "children",
        "family",
        "danger"
    ],

    "high": [
        "project l",
        "recovery",
        "identity",
        "mask",
        "nervous system",
        "trauma",
        "memory"
    ],

    "medium": [
        "future",
        "meaning",
        "philosophy",
        "growth",
        "healing"
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

            data = json.loads(path.read_text(encoding="utf-8"))

            for m in data.get("memories", []):

                text = normalize(m.get("content"))

                if len(text) < 30:
                    continue

                memories.append({
                    "text": text,
                    "source": path.name
                })

        except:
            pass

    return memories

def score_memory(text):

    lowered = text.lower()

    score = 0
    level = "low"

    for p in PRIORITY_RULES["critical"]:
        if p in lowered:
            score += 100

    for p in PRIORITY_RULES["high"]:
        if p in lowered:
            score += 35

    for p in PRIORITY_RULES["medium"]:
        if p in lowered:
            score += 15

    if len(text) > 400:
        score += 10

    if score >= 100:
        level = "critical"

    elif score >= 45:
        level = "high"

    elif score >= 15:
        level = "medium"

    return level, score

def run():

    print("")
    print("Loading memories...")

    memories = load_memories()

    print(f"Memories loaded: {len(memories)}")

    grouped = defaultdict(list)

    for m in memories:

        level, score = score_memory(m["text"])

        grouped[level].append({
            "score": score,
            "text": m["text"][:600]
        })

    for k in grouped:
        grouped[k] = sorted(
            grouped[k],
            key=lambda x: x["score"],
            reverse=True
        )[:250]

    out = {
        "created_at": str(datetime.utcnow()),
        "priority_memory": dict(grouped)
    }

    out_path = OUT_DIR / "active_priority_memory.json"

    out_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"active_priority_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Priority engine complete.")
    print(f"Report written to: {report_path}")
    print("")

    print("Summary:")

    for level in ["critical", "high", "medium", "low"]:

        print(f"  {level}: {len(grouped[level])}")

    print("")

if __name__ == "__main__":
    run()

