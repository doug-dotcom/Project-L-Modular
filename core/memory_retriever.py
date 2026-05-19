from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = ROOT / "memory"

DOMAIN_HINTS = {
    "sport": [
        "sport","hockey","team","game","training",
        "fullback","masters","wolves"
    ],
    "family": [
        "kids","children","daughter","son","family",
        "iyla","isla","ashton","luella","mehlia"
    ],
    "recovery": [
        "recovery","aa","na","meeting","sponsor",
        "step","sobriety","clean","addiction"
    ],
    "health": [
        "health","adhd","ptsd","anxiety","depression",
        "therapy","doctor","pauline"
    ],
    "identity": [
        "who am i","identity","purpose","meaning",
        "mask","self","doug","dougie"
    ],
    "emotional": [
        "emotion","lonely","sad","grief","fear",
        "abandonment","vulnerable"
    ]
}

def normalise(text):
    return re.sub(r"\s+", " ", str(text).lower())

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None

def detect_domains(query):
    q = normalise(query)

    scores = {}

    for domain, hints in DOMAIN_HINTS.items():
        score = 0

        for h in hints:
            if h in q:
                score += 3

        scores[domain] = score

    selected = [
        d for d, s in
        sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if s > 0
    ]

    if not selected:
        selected = [
            "identity",
            "general",
            "family",
            "sport",
            "health",
            "recovery",
            "emotional"
        ]

    return selected[:4]

def extract_memories(data):

    memories = []

    if isinstance(data, dict):

        if "memories" in data:
            memories.extend(data["memories"])

        else:
            memories.append(data)

    elif isinstance(data, list):
        memories.extend(data)

    return memories

def calculate_score(mem, query, domain_boost=0):

    q = normalise(query)

    text = normalise(mem.get("content", ""))

    overlap = 0

    for word in q.split():

        if len(word) < 3:
            continue

        if word in text:
            overlap += 1

    importance = float(mem.get("importance", 0.5))
    reinforcement = float(mem.get("reinforcement", 0.0))

    score = (
        overlap * 5
        + importance * 2
        + reinforcement
        + domain_boost
    )

    return score

def retrieve_memory_context(query, limit=12):

    domains = detect_domains(query)

    candidates = []

    search_paths = []

    for domain in domains:

        search_paths.append(
            MEMORY_DIR / "domains" / f"{domain}.json"
        )

    fallback_files = [
        MEMORY_DIR / "domains" / "general.json",
        MEMORY_DIR / "domains" / "identity.json",
        MEMORY_DIR / "domains" / "family.json",
        MEMORY_DIR / "domains" / "sport.json",
        MEMORY_DIR / "recovery" / "recovery_patterns.json",
        MEMORY_DIR / "emotional" / "emotional_state.json"
    ]

    for p in fallback_files:

        if p not in search_paths:
            search_paths.append(p)

    for path in search_paths:

        if not path.exists():
            continue

        data = load_json(path)

        if not data:
            continue

        memories = extract_memories(data)

        domain_boost = 2 if any(
            d in path.name for d in domains
        ) else 0

        for mem in memories:

            score = calculate_score(
                mem,
                query,
                domain_boost
            )

            if score > 0:

                candidates.append({
                    "score": score,
                    "memory": mem,
                    "source": path.name
                })

    ranked = sorted(
        candidates,
        key=lambda x: x["score"],
        reverse=True
    )

    merged = []

    seen = set()

    for item in ranked:

        content = item["memory"].get("content", "")

        if content in seen:
            continue

        seen.add(content)

        merged.append({
            "content": content,
            "score": item["score"],
            "source": item["source"]
        })

    merged = merged[:limit]

    context = "\n".join([
        f"- {m['content']}"
        for m in merged
    ])

    return {
        "domains": domains,
        "memories": merged,
        "context": context
    }
