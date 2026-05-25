import os
import json
import re
from pathlib import Path
from datetime import datetime

# ============================================================
# ROOT
# ============================================================

ROOT = Path(r"C:\Shine_L")

MEMORY_DIR = ROOT / "memory"
DOMAIN_DIR = MEMORY_DIR / "domains"
PENDING_DIR = MEMORY_DIR / "pending"

QUEUE_FILE = PENDING_DIR / "pending_memory_queue.json"

DOMAIN_DIR.mkdir(parents=True, exist_ok=True)
PENDING_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# DOMAIN FILES
# ============================================================

DOMAINS = {
    "identity": [],
    "family": [],
    "health": [],
    "recovery": [],
    "relationships": [],
    "project_l": [],
    "sport": [],
    "finance": [],
    "general": []
}

# ============================================================
# LOAD JSON SAFE
# ============================================================

def load_json(path):

    try:

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except:
        return []

# ============================================================
# SAVE JSON SAFE
# ============================================================

def save_json(path, data):

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ============================================================
# CAROL CLEANER
# Removes junk / duplicates / low signal
# ============================================================

def carol_cleaner(memories):

    print("\n=== CAROL CLEANER RUNNING ===")

    cleaned = []
    seen = set()

    for memory in memories:

        if not isinstance(memory, dict):
            continue

        content = str(memory.get("content", "")).strip()

        if len(content) < 20:
            continue

        content_norm = content.lower()

        # Remove duplicates
        if content_norm in seen:
            continue

        seen.add(content_norm)

        # Remove obvious junk
        junk_patterns = [
            "ok",
            "lol",
            "haha",
            "cool",
            "nice",
            "thanks",
            "👍",
            "😂"
        ]

        if content_norm in junk_patterns:
            continue

        cleaned.append(memory)

    print(f"Carol cleaned memories: {len(cleaned)}")

    return cleaned

# ============================================================
# SALLY SALIENCE
# Assigns importance score
# ============================================================

def sally_salience(memory):

    content = str(memory.get("content", "")).lower()

    score = 0

    high_salience_keywords = [
        "identity",
        "trauma",
        "recovery",
        "adhd",
        "ocpd",
        "cptsd",
        "emotional safety",
        "project l",
        "children",
        "daughter",
        "son",
        "family",
        "meaning",
        "salience",
        "continuity",
        "memory",
        "autonomy",
        "relationship",
        "philosophy",
        "reflection",
        "psychology",
        "pauline",
        "leah",
        "lyndal",
        "father",
        "mother",
        "army",
        "hockey",
        "truth",
        "authenticity"
    ]

    for keyword in high_salience_keywords:

        if keyword in content:
            score += 10

    # Longer deeper reflections
    score += min(len(content) // 150, 15)

    # Emotional weighting
    emotional_words = [
        "hurt",
        "fear",
        "love",
        "ashamed",
        "safe",
        "unsafe",
        "growth",
        "reflection",
        "insight",
        "breakthrough"
    ]

    for word in emotional_words:

        if word in content:
            score += 5

    return score

# ============================================================
# DOMAIN ROUTER
# ============================================================

def route_memory(memory):

    content = str(memory.get("content", "")).lower()

    if any(x in content for x in [
        "identity",
        "meaning",
        "philosophy",
        "authenticity",
        "autonomy",
        "salience"
    ]):
        return "identity"

    if any(x in content for x in [
        "daughter",
        "son",
        "mum",
        "mother",
        "dad",
        "father",
        "family",
        "kids",
        "iyla",
        "ashton",
        "luella",
        "mehlia"
    ]):
        return "family"

    if any(x in content for x in [
        "adhd",
        "ocpd",
        "cptsd",
        "anxiety",
        "depression",
        "mental health",
        "psychologist"
    ]):
        return "health"

    if any(x in content for x in [
        "na",
        "recovery",
        "clean",
        "step work",
        "using dreams",
        "addiction"
    ]):
        return "recovery"

    if any(x in content for x in [
        "leah",
        "lyndal",
        "relationship",
        "girlfriend",
        "friend",
        "paul"
    ]):
        return "relationships"

    if any(x in content for x in [
        "project l",
        "shine",
        "memory architecture",
        "cognition",
        "recursive",
        "ai"
    ]):
        return "project_l"

    if any(x in content for x in [
        "hockey",
        "sport",
        "netball"
    ]):
        return "sport"

    if any(x in content for x in [
        "finance",
        "money",
        "tpd",
        "super",
        "capstone"
    ]):
        return "finance"

    return "general"

# ============================================================
# LOAD QUEUE
# ============================================================

print("\n=== LOADING PENDING QUEUE ===")

memories = load_json(QUEUE_FILE)

print(f"Raw memories loaded: {len(memories)}")

# ============================================================
# CAROL CLEANER
# ============================================================

memories = carol_cleaner(memories)

# ============================================================
# SALLY SALIENCE
# ============================================================

print("\n=== SALLY SALIENCE RUNNING ===")

for memory in memories:

    memory["salience_score"] = sally_salience(memory)

# ============================================================
# SORT BY SALIENCE
# ============================================================

memories = sorted(
    memories,
    key=lambda x: x.get("salience_score", 0),
    reverse=True
)

# ============================================================
# ROUTE INTO DOMAINS
# ============================================================

print("\n=== ROUTING DOMAINS ===")

for memory in memories:

    domain = route_memory(memory)

    if domain not in DOMAINS:
        domain = "general"

    DOMAINS[domain].append(memory)

# ============================================================
# SAVE DOMAIN FILES
# ============================================================

print("\n=== SAVING DOMAIN FILES ===")

for domain, data in DOMAINS.items():

    path = DOMAIN_DIR / f"{domain}.json"

    save_json(path, data)

    print(f"{domain}: {len(data)} memories")

# ============================================================
# SUMMARY
# ============================================================

print("\n=== REBUILD COMPLETE ===")

total = sum(len(v) for v in DOMAINS.values())

print(f"Total routed memories: {total}")

print("\nTop Salience Memories:\n")

for memory in memories[:10]:

    print(
        f"[{memory.get('salience_score',0)}] "
        f"{memory.get('content','')[:120]}"
    )
