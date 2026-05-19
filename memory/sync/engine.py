from supabase import create_client
from dotenv import load_dotenv
from pathlib import Path
import os
import json
from datetime import datetime

# ============================================
# LOAD ENV
# ============================================

ROOT = Path("C:/Shine_L")

load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: Missing Supabase credentials")
    exit()

# ============================================
# CONNECT
# ============================================

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================
# PATHS
# ============================================

pending_path = ROOT / "memory" / "pending" / "pending_memory_queue.json"

if not pending_path.exists():
    pending_path.write_text("[]", encoding="utf-8")

# ============================================
# LOAD EXISTING MEMORY
# ============================================

try:
    existing = json.loads(pending_path.read_text(encoding="utf-8"))
except:
    existing = []

existing_ids = set()

for item in existing:
    if "id" in item:
        existing_ids.add(item["id"])

# ============================================
# PULL FROM SUPABASE
# ============================================

print("Pulling memories from Supabase...")

response = (
    supabase
    .table("raw_catchall")
    .select("*")
    .order("created_at")
    .execute()
)

rows = response.data

new_rows = []

for row in rows:

    row_id = row.get("id")

    if row_id not in existing_ids:
        new_rows.append(row)

# ============================================
# APPEND NEW ROWS
# ============================================

if new_rows:

    existing.extend(new_rows)

    pending_path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"SUCCESS: Added {len(new_rows)} new memories.")

else:
    print("No new memories found.")

print(f"Total pending memories: {len(existing)}")

# ============================================
# DONE
# ============================================

print("Memory ingestion complete.")
