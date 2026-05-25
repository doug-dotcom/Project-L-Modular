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
# LOAD ENV
# ============================================================

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except:
    pass

# ============================================================
# SUPABASE
# ============================================================

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE credentials.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================
# DOMAIN STRUCTURE
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

        if not isinstance(memory, dict):
            continue

        content = str(memory.get("content", "")).strip()

        if len(content) < 20:
            continue

        normalized = content.lower()

        if normalized in seen:
            continue

        seen.add(normalized)

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

        if normalized in junk:
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

    high_salience = [
        "identity",
        "salience",
        "project l",
        "continuity",
        "emotional safety",
        "autonomy",
        "truth",
        "authenticity",
        "memory",
        "recursive",
        "reflection",
        "adhd",
        "cptsd",
        "ocpd",
        "trauma",
        "family",
        "children",
        "daughter",
        "recovery",
        "na",
        "philosophy",
        "pauline",
        "leah",
        "lyndal",
        "army",
        "hockey",
        "psychology",
        "meaning",
        "growth"
    ]

    emotional_words = [
        "hurt",
        "fear",
        "safe",
        "unsafe",
        "ashamed",
        "love",
        "connection",
        "insight",
        "breakthrough",
        "reflection"
    ]

    for word in high_salience:

        if word in content:
            score += 10

    for word in emotional_words:

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
        "meaning",
        "philosophy",
        "autonomy",
        "salience",
        "truth",
        "authenticity"
    ]):
        return "identity"

    if any(x in content for x in [
        "daughter",
        "son",
        "kids",
        "mum",
        "mother",
        "dad",
        "father",
        "family",
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
        "friend",
        "girlfriend",
        "paul"
    ]):
        return "relationships"

    if any(x in content for x in [
        "project l",
        "shine",
        "cognition",
        "recursive",
        "memory architecture",
        "ai"
    ]):
        return "project_l"

    if any(x in content for x in [
        "hockey",
        "netball",
        "sport"
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
# PULL RAW_CATCHALL
# ============================================================

print("\n=== PULLING RAW_CATCHALL FROM SUPABASE ===")

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

    memory = {
        "content": content,
        "timestamp": row.get("created_at"),
        "session_id": row.get("session_id"),
        "role": row.get("role"),
        "source": "supabase_raw_catchall"
    }

    memories.append(memory)

# ============================================================
# CAROL CLEANER
# ============================================================

memories = carol_cleaner(memories)

# ============================================================
# SALLY SALIENCE
# ============================================================

print("\n=== SALLY SALIENCE ===")

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
# ROUTE DOMAINS
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

print("\n=== SAVING DOMAINS ===")

for domain, data in DOMAINS.items():

    path = DOMAIN_DIR / f"{domain}.json"

    save_json(path, data)

    print(f"{domain}: {len(data)}")

# ============================================================
# SUMMARY
# ============================================================

print("\n=== TOP SALIENCE MEMORIES ===\n")

for memory in memories[:15]:

    print(
        f"[{memory.get('salience_score',0)}] "
        f"{memory.get('content','')[:120]}"
    )

print("\n=== MEMORY REBUILD COMPLETE ===")
