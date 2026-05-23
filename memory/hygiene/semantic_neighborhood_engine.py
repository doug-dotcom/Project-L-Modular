import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

DOMAIN_DIR = ROOT / "memory" / "domains"
REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"
NEIGHBOR_DIR = ROOT / "memory" / "neighborhoods"

NEIGHBOR_RULES = {

    "mask_identity": [
        "mask","armor","identity","dougie",
        "douglas","self-worth","abandonment"
    ],

    "recovery_rooms": [
        "recovery","aa","na","meetings",
        "sponsor","step","sobriety"
    ],

    "project_l_cognition": [
        "project l","memory","semantic",
        "cognition","active cognition",
        "vector","orchestration"
    ],

    "nervous_system": [
        "nervous system","polyvagal",
        "trauma","freeze","fight",
        "flight","shutdown"
    ],

    "future_fear": [
        "if/when","future","stuck",
        "waiting","uncertainty",
        "survival mode"
    ],

    "family_core": [
        "children","family","iyla",
        "ashton","luella","mehlia"
    ],

    "philosophy_meaning": [
        "meaning","truth","flow",
        "consciousness","philosophy",
        "humanity"
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

def detect_neighborhood(text):

    lowered = text.lower()

    scores = defaultdict(int)

    for hood, patterns in NEIGHBOR_RULES.items():
        for p in patterns:
            if p.lower() in lowered:
                scores[hood] += 1

    if not scores:
        return "unclustered"

    return max(scores, key=scores.get)

def load_domains():

    memories = []

    if not DOMAIN_DIR.exists():
        return memories

    for path in DOMAIN_DIR.glob("*.json"):

        try:
            data = json.loads(path.read_text(encoding="utf-8"))

            for m in data.get("memories", []):

                content = normalize(m.get("content"))

                memories.append({
                    "source": str(path.name),
                    "content": content
                })

        except:
            pass

    return memories

def run():

    print("")
    print("Loading domain memories...")

    memories = load_domains()

    print(f"Memories loaded: {len(memories)}")

    neighborhoods = defaultdict(list)

    for m in memories:

        hood = detect_neighborhood(m["content"])

        neighborhoods[hood].append(m)

    report = {
        "created_at": str(datetime.utcnow()),
        "total_memories": len(memories),
        "neighborhoods": {}
    }

    for hood, items in neighborhoods.items():

        export = {
            "neighborhood": hood,
            "memory_count": len(items),
            "memories": items[:500]
        }

        outpath = NEIGHBOR_DIR / f"{hood}.json"

        outpath.write_text(
            json.dumps(export, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        report["neighborhoods"][hood] = len(items)

    report_path = REPORT_DIR / f"semantic_neighborhood_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Semantic neighborhoods complete.")
    print(f"Report written to: {report_path}")
    print("")
    print("Summary:")

    for k,v in sorted(report["neighborhoods"].items(), key=lambda x: x[1], reverse=True):
        print(f"  {k}: {v}")

    print("")

if __name__ == "__main__":
    run()

