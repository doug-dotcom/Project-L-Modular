import json
from pathlib import Path
from datetime import datetime

ROOT = Path("C:/Shine_L")

pending_path = ROOT / "memory" / "pending" / "pending_memory_queue.json"

paths = {
    "identity": ROOT / "memory" / "domains" / "identity.json",
    "family": ROOT / "memory" / "domains" / "family.json",
    "work": ROOT / "memory" / "domains" / "work.json",
    "sport": ROOT / "memory" / "domains" / "sport.json",
    "health": ROOT / "memory" / "domains" / "health.json",
    "general": ROOT / "memory" / "domains" / "general.json",
    "emotional": ROOT / "memory" / "emotional" / "emotional_state.json",
    "learning": ROOT / "memory" / "learning" / "adaptive_learning.json",
    "patterns": ROOT / "memory" / "patterns" / "memory_patterns.json"
}

rules = {
    "identity": [
        "my values", "honesty", "loyalty", "connection", "i am", "i'm",
        "my goal", "my dream", "i prefer", "important to me", "i believe",
        "i enjoy", "i struggle", "who i am", "identity", "purpose"
    ],
    "family": [
        "family", "kids", "children", "daughter", "son", "isla", "ashton",
        "ash", "malia", "mehlia", "dad", "father", "mum", "mother",
        "parent", "parenting"
    ],
    "work": [
        "anz", "financial planner", "fp", "work", "career", "job",
        "zurich", "tpd", "insurance", "capstone", "afca", "business",
        "finance", "financial", "ato"
    ],
    "sport": [
        "hockey", "sport", "masters", "field hockey", "team", "game",
        "training", "brisbane masters", "kedron", "wolves"
    ],
    "health": [
        "health", "doctor", "gp", "medication", "atomoxetine", "injury",
        "pain", "calf", "back", "muscle", "dementia", "adhd", "sleep"
    ],
    "emotional": [
        "feel", "feeling", "grateful", "sad", "lonely", "fear", "afraid",
        "anxious", "overwhelmed", "tired", "happy", "hurt", "hope",
        "hopeless", "love", "mask", "vulnerable", "shame", "abandonment"
    ],
    "learning": [
        "learn", "learning", "implement", "improve", "growth", "reflection",
        "realisation", "realization", "understanding", "insight", "lesson",
        "takeaway", "teach", "evolve"
    ],
    "patterns": [
        "pattern", "trigger", "cycle", "obsession", "hyperfocus", "recovery",
        "routine", "habit", "schema", "schemas", "drift", "overload",
        "compulsion"
    ]
}

def load_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def normalise_store(data, domain_name):
    if isinstance(data, list):
        return {
            "domain": domain_name,
            "memory_count": len(data),
            "memories": data
        }

    if isinstance(data, dict):
        if "memories" not in data or not isinstance(data["memories"], list):
            data["memories"] = []
        data["domain"] = data.get("domain", domain_name)
        data["memory_count"] = len(data["memories"])
        return data

    return {
        "domain": domain_name,
        "memory_count": 0,
        "memories": []
    }

def save_store(path, store):
    store["memory_count"] = len(store.get("memories", []))
    store["last_updated"] = datetime.now().isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")

def memory_text(item):
    raw = item.get("content", "")
    if isinstance(raw, (dict, list)):
        return json.dumps(raw, ensure_ascii=False).lower()
    return str(raw).lower()

pending = load_json(pending_path, [])

if not isinstance(pending, list):
    print("ERROR: pending_memory_queue.json is not a list.")
    raise SystemExit(1)

stores = {}
for name, path in paths.items():
    stores[name] = normalise_store(load_json(path, {}), name)

processed = 0
route_counts = {name: 0 for name in paths.keys()}

for item in pending:
    text = memory_text(item)
    routed_any = False

    for category, keywords in rules.items():
        if any(k in text for k in keywords):
            stores[category]["memories"].append(item)
            route_counts[category] += 1
            routed_any = True

    if not routed_any:
        stores["general"]["memories"].append(item)
        route_counts["general"] += 1

    processed += 1

for name, path in paths.items():
    save_store(path, stores[name])

pending_path.write_text("[]", encoding="utf-8")

print("")
print("==============================================")
print("STAGE 2.1 MEMORY FILING COMPLETE")
print("==============================================")
print(f"Processed: {processed}")
for name, count in route_counts.items():
    print(f"{name}: {count}")
print("Pending queue cleared.")
print("==============================================")
