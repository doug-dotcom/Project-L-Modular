import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARY_ROOT = Path(__file__).resolve().parent
DOMAIN_DIR = ROOT / "memory" / "domains"

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e), "path": str(path)}

def normalise_memory_items(raw):
    if isinstance(raw, list):
        return raw

    if isinstance(raw, dict):
        if "memories" in raw and isinstance(raw["memories"], list):
            return raw["memories"]

        return [raw]

    return []

def load_domain(domain_name):
    path = DOMAIN_DIR / f"{domain_name}.json"

    raw = load_json(path)
    memories = normalise_memory_items(raw)

    return {
        "domain": domain_name,
        "path": str(path),
        "memory_count": len(memories),
        "memories": memories
    }

def top_memories(memories, limit=5):
    def score(item):
        return (
            item.get("salience_score")
            or item.get("priority")
            or 0
        )

    return sorted(
        memories,
        key=score,
        reverse=True
    )[:limit]

def process_domain(domain_name):
    domain_packet = load_domain(domain_name)
    memories = domain_packet.get("memories", [])

    packet = {
        "captain": "Mary BridgeSheila",
        "mission": "Connect grouped domain memories to create meaning and context.",
        "domain": domain_name,
        "domain_source_of_truth": domain_packet.get("path"),
        "memory_count": domain_packet.get("memory_count"),
        "top_memories": top_memories(memories),
        "status": "domain_loaded",
        "next_step": "AODS 10 will add mary_processed flags without damaging existing memory structure."
    }

    return packet

if __name__ == "__main__":
    result = process_domain("sport")
    print(json.dumps(result, indent=2, ensure_ascii=False))
