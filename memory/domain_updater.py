import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]

QUEUE_FILE = ROOT / "memory" / "pending" / "pending_memory_queue.json"
DOMAIN_DIR = ROOT / "memory" / "domains"

DOMAIN_ALIASES = {
    "project": "project_l",
    "projects": "project_l",
    "insurance": "work",
    "career": "work",
}

VALID_DOMAINS = {
    "family",
    "identity",
    "work",
    "health",
    "sport",
    "project_l",
    "emotional",
    "general"
}

def load_json(path, fallback):
    try:
        if not path.exists():
            return fallback
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

def normalise_domain(domain):
    domain = str(domain or "general").strip().lower()
    domain = DOMAIN_ALIASES.get(domain, domain)
    if domain not in VALID_DOMAINS:
        return "general"
    return domain

def normalise_content(text):
    return " ".join(str(text or "").strip().split())

def domain_file(domain):
    return DOMAIN_DIR / f"{domain}.json"

def load_domain(domain):
    path = domain_file(domain)
    payload = load_json(path, {
        "domain": domain,
        "memory_count": 0,
        "memories": []
    })

    if "memories" not in payload or not isinstance(payload["memories"], list):
        payload["memories"] = []

    payload["domain"] = domain
    return payload

def write_domain(domain, payload):
    memories = payload.get("memories", [])

    memories.sort(
        key=lambda x: float(x.get("importance", 0) or 0),
        reverse=True
    )

    payload["memory_count"] = len(memories)
    payload["updated_at"] = str(datetime.now())

    save_json(domain_file(domain), payload)

def memory_exists(memories, content):
    target = normalise_content(content).lower()

    for mem in memories:
        existing = normalise_content(mem.get("content", "")).lower()
        if existing == target:
            return True

    return False

def safe_update_domains():
    queue = load_json(QUEUE_FILE, [])

    written = 0
    skipped = 0
    domains_touched = set()

    for item in queue:
        if item.get("status") not in [
           "classified",
           "compressed",
           "ready_for_write"
	]:
    continue

        content = normalise_content(
            item.get("compressed_content") or item.get("content")
        )

        if not content:
            item["status"] = "skipped"
            item["skip_reason"] = "empty content"
            skipped += 1
            continue

        domain = normalise_domain(
            item.get("proposed_domain", "general")
        )

        payload = load_domain(domain)
        memories = payload.get("memories", [])

        if memory_exists(memories, content):
            item["status"] = "duplicate"
            item["written_domain"] = domain
            item["updated_at"] = str(datetime.now())
            skipped += 1
            continue

        entry = {
            "content": content,
            "importance": float(item.get("importance", 3) or 3),
            "category": domain,
            "source": "adaptive_memory_queue",
            "created_at": str(datetime.now())
        }

        memories.append(entry)
        payload["memories"] = memories

        write_domain(domain, payload)

        item["status"] = "written"
        item["written_domain"] = domain
        item["written_at"] = str(datetime.now())

        written += 1
        domains_touched.add(domain)

    save_json(QUEUE_FILE, queue)

    return {
        "status": "ok",
        "written": written,
        "skipped": skipped,
        "domains_touched": sorted(list(domains_touched)),
        "queue_size": len(queue)
    }

def domain_updater_status():
    queue = load_json(QUEUE_FILE, [])

    counts = {}
    for item in queue:
        status = item.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1

    domains = []
    if DOMAIN_DIR.exists():
        domains = sorted([p.name for p in DOMAIN_DIR.glob("*.json")])

    return {
        "status": "online",
        "operation": "AODS-108",
        "queue_status_counts": counts,
        "domains": domains
    }
