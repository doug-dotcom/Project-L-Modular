import json
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

SEARCH_DIRS = [
    ROOT / "memory",
    ROOT / "continuity",
    ROOT / "semantic_index"
]

REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"
DOMAIN_DIR = ROOT / "memory" / "domains"

DOMAIN_RULES = {
    "recovery": [
        "recovery","aa","na","meetings","sponsor",
        "step","addiction","sobriety","mask",
        "if/when","emotional exhaustion","pauline"
    ],

    "identity": [
        "doug","dougie","douglas","identity",
        "self-worth","meaning","truth",
        "consciousness","flow"
    ],

    "family": [
        "iyla","ashton","luella","mehlia",
        "family","children","daughter","son",
        "tamara","leah"
    ],

    "project_l": [
        "project l","memory","semantic",
        "cognition","orchestration","vector",
        "active cognition","canonical"
    ],

    "psychology": [
        "schema","jung","freud","rogers",
        "porges","trauma","nervous system",
        "attachment","polyvagal"
    ],

    "military": [
        "army","east timor","military",
        "deployment","service"
    ],

    "philosophy": [
        "philosophy","tao","stoicism",
        "existential","alan watts",
        "harari","bostrom","crawford"
    ],

    "sport": [
        "hockey","sport","training",
        "gym","exercise"
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

def detect_domain(text):
    lowered = text.lower()

    scores = defaultdict(int)

    for domain, patterns in DOMAIN_RULES.items():
        for p in patterns:
            if p.lower() in lowered:
                scores[domain] += 1

    if not scores:
        return "unclassified"

    return max(scores, key=scores.get)

def collect_memories():
    items = []

    for base in SEARCH_DIRS:
        if not base.exists():
            continue

        for path in base.rglob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))

                if isinstance(data, list):
                    for x in data:
                        items.append({
                            "source": str(path),
                            "content": normalize(x)
                        })

                elif isinstance(data, dict):

                    if "memories" in data:
                        for m in data["memories"]:
                            items.append({
                                "source": str(path),
                                "content": normalize(m)
                            })

                    else:
                        items.append({
                            "source": str(path),
                            "content": normalize(data)
                        })

            except:
                pass

    return items

def run():

    print("")
    print("Collecting memories...")

    memories = collect_memories()

    print(f"Memories collected: {len(memories)}")

    domains = defaultdict(list)

    for m in memories:
        domain = detect_domain(m["content"])
        domains[domain].append(m)

    report = {
        "created_at": str(datetime.utcnow()),
        "total_memories": len(memories),
        "domains": {}
    }

    for domain, items in domains.items():

        export = {
            "domain": domain,
            "memory_count": len(items),
            "memories": items[:500]
        }

        outpath = DOMAIN_DIR / f"{domain}.json"

        outpath.write_text(
            json.dumps(export, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        report["domains"][domain] = len(items)

    report_path = REPORT_DIR / f"domain_segmentation_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Domain segmentation complete.")
    print(f"Report written to: {report_path}")
    print("")
    print("Summary:")

    for k,v in sorted(report["domains"].items(), key=lambda x: x[1], reverse=True):
        print(f"  {k}: {v}")

    print("")

if __name__ == "__main__":
    run()

