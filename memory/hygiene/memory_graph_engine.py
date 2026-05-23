import json
import re
from pathlib import Path
from collections import defaultdict
from itertools import combinations
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

DOMAIN_DIR = ROOT / "memory" / "domains"
GRAPH_DIR = ROOT / "memory" / "graph"
REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"

ENTITY_PATTERNS = {

    "doug": [
        "doug",
        "dougie",
        "douglas"
    ],

    "recovery": [
        "recovery",
        "meetings",
        "aa",
        "na",
        "step"
    ],

    "identity": [
        "identity",
        "mask",
        "armour",
        "armor",
        "self-worth"
    ],

    "project_l": [
        "project l",
        "l",
        "memory",
        "ai",
        "shine"
    ],

    "nervous_system": [
        "nervous system",
        "polyvagal",
        "regulation",
        "co-regulation"
    ],

    "future_fear": [
        "if/when",
        "future",
        "stuck",
        "limbo"
    ],

    "family": [
        "kids",
        "children",
        "family",
        "ashton",
        "luella",
        "iyla"
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

                content = normalize(m.get("content"))

                memories.append(content)

        except:
            pass

    return memories

def detect_entities(text):

    lowered = text.lower()

    found = []

    for entity, patterns in ENTITY_PATTERNS.items():

        for p in patterns:

            if p.lower() in lowered:
                found.append(entity)
                break

    return list(set(found))

def build_graph(memories):

    graph = defaultdict(int)

    for text in memories:

        entities = detect_entities(text)

        if len(entities) < 2:
            continue

        for a, b in combinations(sorted(entities), 2):

            key = f"{a} <-> {b}"

            graph[key] += 1

    return graph

def run():

    print("")
    print("Loading memories...")

    memories = load_memories()

    print(f"Memories loaded: {len(memories)}")

    graph = build_graph(memories)

    sorted_graph = dict(
        sorted(
            graph.items(),
            key=lambda x: x[1],
            reverse=True
        )
    )

    out = {
        "created_at": str(datetime.utcnow()),
        "relationships": sorted_graph
    }

    graph_path = GRAPH_DIR / "memory_relationship_graph.json"

    graph_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"memory_graph_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Memory graph complete.")
    print(f"Graph written to: {graph_path}")
    print("")
    print("Top Relationships:")

    top = list(sorted_graph.items())[:15]

    for k,v in top:
        print(f"  {k}: {v}")

    print("")

if __name__ == "__main__":
    run()

