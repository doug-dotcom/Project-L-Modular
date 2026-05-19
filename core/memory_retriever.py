import json
import os
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = ROOT / "memory"

DOMAIN_HINTS = {
    "sport": [
        "sport", "hockey", "field hockey", "team", "play", "masters",
        "division", "kedron", "wolves", "fullback", "netball"
    ],
    "health": [
        "health", "doctor", "medical", "meds", "diagnosis", "adhd",
        "ptsd", "asthma", "anxiety", "depression", "pain"
    ],
    "family": [
        "kids", "children", "daughter", "son", "family", "isla",
        "iyla", "ashton", "luella", "mehlia", "mala"
    ],
    "recovery": [
        "recovery", "aa", "na", "meeting", "sponsor", "step",
        "clean", "sober", "addiction", "alcohol", "fellowship"
    ],
    "identity": [
        "me", "who am i", "about me", "identity", "values",
        "truth", "doug", "dougie", "douglas", "shine", "l"
    ],
    "emotional": [
        "feel", "feeling", "emotion", "sad", "lonely", "mask",
        "abandonment", "fear", "vulnerable", "overwhelmed"
    ],
    "general": [
        "remember", "tell me", "what do you know", "life", "story"
    ]
}


def _normalise(text):
    return re.sub(r"[^a-z0-9\s]", " ", str(text).lower())


def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _extract_memories(obj):
    memories = []

    if isinstance(obj, dict):
        if "memories" in obj and isinstance(obj["memories"], list):
            for m in obj["memories"]:
                if isinstance(m, dict):
                    content = m.get("content") or m.get("text") or m.get("memory")
                    if content:
                        memories.append({
                            "content": str(content),
                            "category": m.get("category", ""),
                            "importance": float(m.get("importance", 0.5) or 0.5),
                            "source": m.get("source", "")
                        })
                elif isinstance(m, str):
                    memories.append({
                        "content": m,
                        "category": "",
                        "importance": 0.5,
                        "source": ""
                    })

        for v in obj.values():
            if isinstance(v, (dict, list)):
                memories.extend(_extract_memories(v))

    elif isinstance(obj, list):
        for item in obj:
            memories.extend(_extract_memories(item))

    return memories


def _score_memory(query, memory):
    q = _normalise(query)
    c = _normalise(memory.get("content", ""))

    q_words = set(q.split())
    c_words = set(c.split())

    if not q_words or not c_words:
        return 0

    overlap = len(q_words.intersection(c_words))
    score = overlap * 3

    # Boost exact useful phrases
    for phrase in [
        "field hockey", "kedron wavell", "wolves", "masters hockey",
        "aa", "na", "pauline", "children", "kids", "adhd", "ptsd"
    ]:
        if phrase in q and phrase in c:
            score += 10
        elif phrase in c and any(w in q for w in phrase.split()):
            score += 4

    score += float(memory.get("importance", 0.5)) * 2

    return score


def detect_domains(query):
    q = _normalise(query)
    scores = {}

    for domain, hints in DOMAIN_HINTS.items():
        score = 0
        for h in hints:
            if h in q:
                score += 3
        scores[domain] = score

    selected = [d for d, s in sorted(scores.items(), key=lambda x: x[1], reverse=True) if s > 0]

    if not selected:
        selected = ["identity", "general", "family", "sport", "health", "recovery", "emotional"]

    return selected[:4]


def retrieve_memory_context(query, limit=12):
    domains = detect_domains(query)
    candidates = []

    search_paths = []

    for domain in domains:
        search_paths.append(MEMORY_DIR / "domains" / f"{domain}.json")

    # Always include identity/general/family/sport as light fallback
    fallback_files = [
        MEMORY_DIR / "domains" / "identity.json",
        MEMORY_DIR / "domains" / "general.json",
        MEMORY_DIR / "domains" / "family.json",
        MEMORY_DIR / "domains" / "sport.json",
        MEMORY_DIR / "recovery" / "recovery_patterns.json",
        MEMORY_DIR / "emotional" / "emotional_state.json",
    ]

    for p in fallback_files:
        if p not in search_paths:
            search_paths.append(p)

    for path in search_paths:
        if not path.exists():
            continue

        data = _load_json(path)
        if data is None:
            continue

        for mem in _extract_memories(data):
            mem["file"] = str(path.relative_to(ROOT))
            mem["score"] = _score_memory(query, mem)
            if mem["score"] > 0:
                candidates.append(mem)

    candidates.sort(key=lambda x: x["score"], reverse=True)

    top = candidates[:limit]

    if not top:
        return {
            "query": query,
            "domains": domains,
            "memories": [],
            "context": ""
        }

    lines = []
    for i, mem in enumerate(top, 1):
        lines.append(f"{i}. {mem['content']}")

    context = "\n".join(lines)

    return {
        "query": query,
        "domains": domains,
        "memories": top,
        "context": context
    }


def build_memory_injection(query):
    result = retrieve_memory_context(query)

    if not result["context"]:
        return ""

    return f"""
RELEVANT MEMORY CONTEXT:
{result["context"]}

INSTRUCTION:
Use the memory context above when directly relevant.
Do not say you have no memory if the answer is present in memory context.
Answer naturally, warmly, and concisely.
"""
