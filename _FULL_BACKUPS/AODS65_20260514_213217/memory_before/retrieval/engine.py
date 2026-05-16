
from orchestration.lieutenants.retrieval_lieutenant import (
    RETRIEVAL_LIEUTENANT,
)
# ============================================================
# MEMORY RETRIEVAL ENGINE
# Operation Mnemosyne
# ============================================================

from pathlib import Path
import json

ROOT = Path(r"C:\Shine_L")
CAPTAINS_DIR = ROOT / "memory" / "captains"


def safe_load_json(path, fallback):

    try:
        if not path.exists():
            return fallback

        return json.loads(
            path.read_text(encoding="utf-8")
        )

    except Exception as e:
        print("RETRIEVAL LOAD ERROR:", e)
        return fallback


def collect_captain_memory_entries():

    entries = []

    if not CAPTAINS_DIR.exists():
        return entries

    for file in CAPTAINS_DIR.rglob("*.json"):

        data = safe_load_json(file, {})

        for item in data.get("entries", []):

            entries.append({
                "source_file": str(file),
                "entry": item
            })

    return entries


def search_local_memory(query, limit=10):

    q = query.lower().strip()

    results = []

    for item in collect_captain_memory_entries():

        blob = json.dumps(
            item.get("entry", {}),
            ensure_ascii=False
        ).lower()

        score = 0

        for word in q.split():
            if word and word in blob:
                score += 1

        if q in blob:
            score += 3

        if score > 0:
            copy = dict(item)
            copy["_score"] = score
            results.append(copy)

    results.sort(
        key=lambda x: x.get("_score", 0),
        reverse=True
    )

    results = results[:limit]

results = (
    RETRIEVAL_LIEUTENANT
    .process_retrieval(results)
)

return results


def build_retrieval_context(query, limit=10):

    results = search_local_memory(
        query,
        limit=limit
    )

    if not results:
        return ""

    lines = []
    lines.append("\n\nRETRIEVED LOCAL MEMORY:")
    lines.append("")

    for item in results:

        entry = item.get("entry", {})

        content = (
            entry.get("content")
            or entry.get("text")
            or entry.get("memory")
            or entry.get("value")
            or str(entry)
        )

        lines.append(
            "- "
            + str(content)[:600]
        )

    return "\n".join(lines)


def retrieval_status():

    return {
        "status": "online",
        "source": "memory/retrieval",
        "operation": "AODS50"
    }

