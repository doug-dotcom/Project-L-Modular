import os
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Shine_L")
MEMORY_DIR = ROOT / "memory"
DOMAIN_DIR = MEMORY_DIR / "domains"
PENDING_DIR = MEMORY_DIR / "pending"
QUEUE_FILE = PENDING_DIR / "pending_memory_queue.json"

DOMAIN_DIR.mkdir(parents=True, exist_ok=True)
PENDING_DIR.mkdir(parents=True, exist_ok=True)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing Supabase credentials in .env")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def salience_score(content):
    text = str(content).lower()
    score = 0

    high = [
        "identity", "truth", "authenticity", "autonomy", "philosophy",
        "project l", "shine", "memory", "cognition", "recursive",
        "adhd", "cptsd", "ocpd", "trauma", "mental health",
        "family", "daughter", "son", "ashton", "luella", "iyla", "mehlia",
        "recovery", "na", "step work", "clean",
        "relationship", "leah", "lyndal", "cassandra", "cass",
        "hockey", "sport", "finance", "tpd", "capstone"
    ]

    emotional = [
        "fear", "hurt", "safe", "unsafe", "love", "ashamed",
        "insight", "breakthrough", "growth", "reflection", "connection"
    ]

    for word in high:
        if word in text:
            score += 10

    for word in emotional:
        if word in text:
            score += 5

    score += min(len(text) // 150, 15)
    return score

def salience_label(score):
    if score >= 35:
        return "high"
    if score >= 15:
        return "medium"
    return "low"

def route_domain(content):
    text = str(content).lower()

    if any(x in text for x in ["identity", "truth", "authenticity", "autonomy", "philosophy", "meaning", "salience"]):
        return "identity"

    if any(x in text for x in ["family", "daughter", "son", "kids", "mum", "mother", "dad", "father", "ashton", "luella", "iyla", "mehlia"]):
        return "family"

    if any(x in text for x in ["adhd", "cptsd", "ocpd", "trauma", "anxiety", "depression", "mental health", "psychologist"]):
        return "health"

    if any(x in text for x in ["recovery", "na", "step work", "clean", "addiction", "using dreams"]):
        return "recovery"

    if any(x in text for x in ["relationship", "leah", "lyndal", "cassandra", "cass", "friend", "girlfriend", "paul"]):
        return "relationships"

    if any(x in text for x in ["project l", "shine", "memory architecture", "cognition", "recursive", "sally", "carol", "connie", "fiona", "tegan", "ai"]):
        return "project_l"

    if any(x in text for x in ["hockey", "sport", "netball"]):
        return "sport"

    if any(x in text for x in ["finance", "money", "tpd", "super", "capstone", "dva"]):
        return "finance"

    return "general"

def is_junk(content):
    text = str(content).strip().lower()
    if len(text) < 20:
        return True
    if text in ["ok", "cool", "nice", "thanks", "lol", "haha", "😂", "👍"]:
        return True
    return False

print("\n=== STEP 1: PULL RAW_CATCHALL ===")

response = (
    supabase
    .table("raw_catchall")
    .select("*")
    .order("created_at", desc=False)
    .limit(5000)
    .execute()
)

rows = response.data or []
print(f"Rows pulled: {len(rows)}")

pending = []

for row in rows:
    content = row.get("content") or row.get("message") or row.get("text") or ""

    pending.append({
        "id": row.get("id"),
        "role": row.get("role"),
        "content": content,
        "created_at": row.get("created_at"),
        "session_id": row.get("session_id"),
        "source": "supabase_raw_catchall"
    })

save_json(QUEUE_FILE, pending)
print(f"Pending queue saved: {QUEUE_FILE}")
print(f"Pending memories: {len(pending)}")

print("\n=== STEP 2: CAROL CLEAN + SALLY SCORE + DOMAIN ROUTE ===")

seen = set()
cleaned = []

for memory in pending:
    content = memory.get("content", "")

    if is_junk(content):
        continue

    norm = str(content).strip().lower()

    if norm in seen:
        continue

    seen.add(norm)

    score = salience_score(content)
    domain = route_domain(content)

    memory["cleaned"] = True
    memory["canonical"] = True
    memory["domain_verified"] = True
    memory["priority"] = 5
    memory["salience_score"] = score
    memory["salience"] = salience_label(score)
    memory["anchor"] = score >= 40
    memory["domain"] = domain
    memory["cleaned_at"] = datetime.now().isoformat()

    cleaned.append(memory)
    DOMAINS[domain].append(memory)

print(f"Carol kept: {len(cleaned)}")
print(f"Duplicates/junk removed: {len(pending) - len(cleaned)}")

print("\n=== STEP 3: SAVE DOMAIN FILES ===")

for domain, data in DOMAINS.items():
    path = DOMAIN_DIR / f"{domain}.json"
    save_json(path, data)
    print(f"{domain}: {len(data)} memories")

print("\n=== TOP 15 SALIENCE MEMORIES ===\n")

for memory in sorted(cleaned, key=lambda x: x.get("salience_score", 0), reverse=True)[:15]:
    print(f"[{memory.get('salience_score')}] [{memory.get('domain')}] {memory.get('content','')[:140]}")

print("\n=== MEMORY CLEAN + DOMAIN REBUILD COMPLETE ===")
print(f"Total raw pulled: {len(pending)}")
print(f"Total cleaned/routed: {len(cleaned)}")
