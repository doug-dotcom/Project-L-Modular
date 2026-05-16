# =====================================================
# runtime_semantic_index_service.py
# AODS 78
# =====================================================

import json
import uuid
from pathlib import Path
from datetime import datetime
from services.runtime_intent_service import dominant_intent

INDEX_DIR = Path("semantic_index")

INDEX_FILE = INDEX_DIR / "semantic_index.json"

MAX_INDEX_ITEMS = 5000

STOP_WORDS = {
    "the", "and", "is", "to", "of",
    "a", "in", "for", "on", "with",
    "that", "this", "it", "as"
}

def ensure_index():

    INDEX_DIR.mkdir(exist_ok=True)

    if not INDEX_FILE.exists():

        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

def load_index():

    ensure_index()

    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []

    except Exception:
        return []

def save_index(items):

    items = items[-MAX_INDEX_ITEMS:]

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)

def tokenize(text):

    text = str(text or "").lower()

    tokens = []

    for token in text.replace("\n", " ").split():

        token = token.strip(".,!?()[]{}:;\"'")

        if (
            token
            and token not in STOP_WORDS
            and len(token) > 2
        ):
            tokens.append(token)

    return sorted(
        list(set(tokens))
    )

def semantic_index(
    label,
    text,
    source_type="general"
):

    items = load_index()

    entry = {
        "index_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "label": label,
        "source_type": source_type,
        "intent": dominant_intent(text),
        "tokens": tokenize(text),
        "preview": str(text)[:300]
    }

    items.append(entry)

    save_index(items)

    return entry

def semantic_search(query):

    query_tokens = tokenize(query)

    results = []

    for item in load_index():

        item_tokens = item.get(
            "tokens",
            []
        )

        overlap = list(
            set(query_tokens)
            & set(item_tokens)
        )

        if overlap:

            results.append({
                "match_score": len(overlap),
                "matched_tokens": overlap,
                "item": item
            })

    results = sorted(
        results,
        key=lambda x: x["match_score"],
        reverse=True
    )

    return results[:25]

def semantic_status():

    items = load_index()

    unique_tokens = set()

    for item in items:

        for token in item.get(
            "tokens",
            []
        ):
            unique_tokens.add(token)

    return {
        "timestamp": datetime.now().isoformat(),
        "indexed_items": len(items),
        "unique_tokens": len(unique_tokens),
        "status": "online"
    }

def recent_index_items(limit=20):

    return load_index()[-limit:]

def semantic_summary():

    status = semantic_status()

    return {
        "timestamp": datetime.now().isoformat(),

        "indexed_items": status.get(
            "indexed_items",
            0
        ),

        "unique_tokens": status.get(
            "unique_tokens",
            0
        ),

        "retrieval_mode": "lightweight_semantic",

        "status": "ready"
    }

