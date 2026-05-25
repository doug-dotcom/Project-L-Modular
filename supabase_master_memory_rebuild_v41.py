import os
import json
from pathlib import Path
from datetime import datetime

# ============================================================
# ROOT
# ============================================================

ROOT = Path(r"C:\Shine_L")

MEMORY_DIR = ROOT / "memory"
DOMAIN_DIR = MEMORY_DIR / "domains"

DOMAIN_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# ENV
# ============================================================

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

# ============================================================
# SUPABASE
# ============================================================

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE credentials.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================
# DOMAINS
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
# SAVE JSON
# ============================================================

def save_json(path, data):

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ============================================================
# CAROL CLEANER
# ============================================================

def carol_cleaner(memories):

    print("\n=== CAROL CLEANER ===")

    cleaned = []
    seen = set()

    for memory in memories:

        content = str(memory.get("content", "")).strip()

        if len(content) < 20:
            continue

        norm = content.lower()

        if norm in seen:
            continue

        seen.add(norm)

        junk = [
            "ok",
            "cool",
            "nice",
            "thanks",
            "lol",
            "haha",
            "😂",
            "👍"
        ]

        if norm in junk:
            continue

        memory["cleaned_at"] = datetime.now().isoformat()

        cleaned.append(memory)

    print(f"Carol kept: {len(cleaned)}")

    return cleaned

# ============================================================
# SALLY SALIENCE
# ============================================================

def sally_salience(memory):

    content = str(memory.get("content", "")).lower()

    score = 0

    important = [
        "identity",
        "salience",
        "project l",
        "continuity",
        "memory",
        "recursive",
        "autonomy",
        "truth",
        "authenticity",
        "recovery",
        "adhd",
        "cptsd",
        "ocpd",
        "family",
        "children",
        "hockey",
        "philosophy",
        "emotional safety",
        "reflection",
        "growth"
    ]

    emotional = [
        "fear",
        "hurt",
        "safe",
        "unsafe",
        "ashamed",
        "love",
        "connection",
        "insight",
        "breakthrough"
    ]

    for word in important:

        if word in content:
            score += 10

    for word in emotional:

        if word in content:
            score += 5

    score += min(len(content) // 150, 15)

    return score

# ============================================================
# DOMAIN ROUTER
# ============================================================

def route_memory(memory):

    content = str(memory.get("content", "")).lower()

    if any(x in content for x in [
        "identity",
        "philosophy",
        "authenticity",
        "truth",
        "salience"
    ]):
        return "identity"

    if any(x in content for x in [
        "family",
        "daughter",
        "son",
        "kids",
        "mum",
        "dad",
        "iyla",
        "ashton",
        "luella",
        "mehlia"
    ]):
        return "family"

    if any(x in content for x in [
        "adhd",
        "cptsd",
        "ocpd",
        "mental health",
        "psychologist"
    ]):
        return "health"

    if any(x in content for x in [
        "recovery",
        "na",
        "clean",
        "step work"
    ]):
        return "recovery"

    if any(x in content for x in [
        "relationship",
        "leah",
        "lyndal",
        "friend",
        "paul"
    ]):
        return "relationships"

    if any(x in content for x in [
        "project l",
        "ai",
        "memory architecture",
        "recursive cognition"
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
        "tpd",
        "super",
        "capstone"
    ]):
        return "finance"

    return "general"

# ============================================================
# PULL RAW_CATCHALL
# ============================================================

print("\n=== PULLING raw_catchall ===")

response = (
    supabase
    .table("raw_catchall")
    .select("*")
    .limit(5000)
    .execute()
)

rows = response.data or []

print(f"Rows pulled: {len(rows)}")

# ============================================================
# NORMALIZE
# ============================================================

memories = []

for row in rows:

    content = (
        row.get("content")
        or row.get("message")
        or row.get("text")
        or ""
    )

    memories.append({
        "content": content,
        "timestamp": row.get("created_at"),
        "session_id": row.get("session_id"),
        "role": row.get("role"),
        "source": "supabase_raw_catchall"
    })

# ============================================================
# CAROL
# ============================================================

memories = carol_cleaner(memories)

# ============================================================
# SALLY
# ============================================================

print("\n=== SALLY SALIENCE ===")

for memory in memories:

    memory["salience_score"] = sally_salience(memory)

# ============================================================
# SORT
# ============================================================

memories = sorted(
    memories,
    key=lambda x: x.get("salience_score", 0),
    reverse=True
)

# ============================================================
# ROUTE
# ============================================================

print("\n=== ROUTING DOMAINS ===")

for memory in memories:

    domain = route_memory(memory)

    if domain not in DOMAINS:
        domain = "general"

    DOMAINS[domain].append(memory)

# ============================================================
# SAVE
# ============================================================

print("\n=== SAVING DOMAIN FILES ===")

for domain, data in DOMAINS.items():

    path = DOMAIN_DIR / f"{domain}.json"

    save_json(path, data)

    print(f"{domain}: {len(data)}")

# ============================================================
# TOP MEMORIES
# ============================================================

print("\n=== TOP SALIENCE MEMORIES ===\n")

for memory in memories[:15]:

    print(
        f"[{memory.get('salience_score',0)}] "
        f"{memory.get('content','')[:120]}"
    )

print("\n=== MEMORY REBUILD COMPLETE ===")
