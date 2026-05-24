import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]

DOMAIN_DIR = ROOT / "memory" / "domains"
QUEUE_FILE = ROOT / "memory" / "pending" / "pending_memory_queue.json"

ANCHOR_WORDS = [
    "children",
    "family",
    "iyla",
    "ashton",
    "luella",
    "mehlia",
    "project l",
    "truth",
    "continuity",
    "memory",
    "tpd",
    "insurance",
    "health",
    "hockey",
    "pauline",
    "terri",
    "shine"
]

def load_json(path, fallback):
    try:
        if not path.exists():
            return fallback
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def save_json(path, data):
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

def normalise(text):
    return " ".join(str(text or "").lower().strip().split())

def similarity_score(a, b):
    a_words = set(normalise(a).split())
    b_words = set(normalise(b).split())

    if not a_words or not b_words:
        return 0

    overlap = len(a_words.intersection(b_words))
    return overlap / max(len(a_words), len(b_words))

def anchor_bonus(content):
    text = normalise(content)
    bonus = 0

    for word in ANCHOR_WORDS:
        if word in text:
            bonus += 0.2

    return min(bonus, 1.5)

def reinforce_domains():
    queue = load_json(QUEUE_FILE, [])

    written_or_duplicate_items = [
        item for item in queue
        if item.get("status") in ["written", "duplicate"]
    ]

    reinforced = 0
    touched_domains = set()

    for domain_file in DOMAIN_DIR.glob("*.json"):

        payload = load_json(domain_file, None)

        if not payload:
            continue

        memories = payload.get("memories", [])

        changed = False

        for mem in memories:

            content = mem.get("content", "")

            if not content:
                continue

            strength = float(mem.get("reinforcement", 0) or 0)
            importance = float(mem.get("importance", 3) or 3)

            # Anchor bonus for core continuity terms
            bonus = anchor_bonus(content)

            if bonus > 0:
                strength += bonus
                importance += bonus * 0.3
                changed = True

            # Reinforce if related to recently queued memories
            for item in written_or_duplicate_items[-100:]:

                candidate = (
                    item.get("compressed_content")
                    or item.get("content")
                    or ""
                )

                score = similarity_score(content, candidate)

                if score >= 0.55:
                    strength += 1
                    importance += 0.5
                    mem["last_reinforced_by"] = candidate[:160]
                    changed = True

            importance = min(10, round(importance, 2))
            strength = round(strength, 2)

            mem["importance"] = importance
            mem["reinforcement"] = strength

            if strength > 0:
                mem["last_reinforced_at"] = str(datetime.now())

        if changed:

            memories.sort(
                key=lambda x: (
                    float(x.get("importance", 0) or 0),
                    float(x.get("reinforcement", 0) or 0)
                ),
                reverse=True
            )

            payload["memories"] = memories
            payload["memory_count"] = len(memories)
            payload["reinforced_at"] = str(datetime.now())

            save_json(domain_file, payload)

            reinforced += 1
            touched_domains.add(domain_file.stem)

    return {
        "status": "ok",
        "domains_reinforced": reinforced,
        "domains_touched": sorted(list(touched_domains))
    }

def reinforcement_status():
    domains = {}

    for domain_file in DOMAIN_DIR.glob("*.json"):

        payload = load_json(domain_file, {})
        memories = payload.get("memories", [])

        reinforced_count = 0

        for mem in memories:
            if float(mem.get("reinforcement", 0) or 0) > 0:
                reinforced_count += 1

        domains[domain_file.stem] = {
            "memory_count": len(memories),
            "reinforced_count": reinforced_count
        }

    return {
        "status": "online",
        "operation": "AODS-109",
        "domains": domains
    }
