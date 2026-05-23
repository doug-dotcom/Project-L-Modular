import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

DOMAIN_DIR = ROOT / "memory" / "domains"
OUT_DIR = ROOT / "memory" / "semantic_promotions"
REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"

PROMOTION_PATTERNS = {

    "conditional_self_worth": [
        "if/when",
        "achievement",
        "safe",
        "whole",
        "productive"
    ],

    "mask_as_survival": [
        "mask",
        "armor",
        "armour",
        "survival adaptation"
    ],

    "recovery_as_regulation": [
        "meetings",
        "co-regulation",
        "recovery",
        "emotional safety"
    ],

    "intellect_as_protection": [
        "systems",
        "psychology",
        "ai",
        "problem-solving",
        "intellectualization"
    ],

    "identity_integration": [
        "dougie",
        "douglas",
        "parts",
        "integration"
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

    items = []

    if not DOMAIN_DIR.exists():
        return items

    for path in DOMAIN_DIR.glob("*.json"):

        try:
            data = json.loads(path.read_text(encoding="utf-8"))

            for m in data.get("memories", []):

                content = normalize(m.get("content"))

                items.append(content)

        except:
            pass

    return items

def detect_promotions(memories):

    promotions = defaultdict(list)

    for text in memories:

        lowered = text.lower()

        for concept, patterns in PROMOTION_PATTERNS.items():

            score = 0

            for p in patterns:
                if p.lower() in lowered:
                    score += 1

            if score >= 2:
                promotions[concept].append(text)

    return promotions

def summarize(texts):

    summaries = []

    for t in texts[:12]:

        if len(t) > 220:
            t = t[:220]

        summaries.append(t)

    return summaries

def run():

    print("")
    print("Loading episodic memories...")

    memories = load_memories()

    print(f"Memories loaded: {len(memories)}")

    promotions = detect_promotions(memories)

    report = {
        "created_at": str(datetime.utcnow()),
        "promotion_candidates": {}
    }

    for concept, items in promotions.items():

        export = {
            "concept": concept,
            "frequency": len(items),
            "candidate_summary": summarize(items),
            "candidate_memories": items[:250]
        }

        outpath = OUT_DIR / f"{concept}.json"

        outpath.write_text(
            json.dumps(export, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        report["promotion_candidates"][concept] = len(items)

    report_path = REPORT_DIR / f"semantic_promotion_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Semantic promotion complete.")
    print(f"Report written to: {report_path}")
    print("")
    print("Summary:")

    for k,v in sorted(report["promotion_candidates"].items(), key=lambda x: x[1], reverse=True):
        print(f"  {k}: {v}")

    print("")

if __name__ == "__main__":
    run()

