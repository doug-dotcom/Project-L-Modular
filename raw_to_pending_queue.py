import os
import json
from pathlib import Path

ROOT = Path(r"C:\Shine_L")

PENDING_DIR = ROOT / "memory" / "pending"
QUEUE_FILE = PENDING_DIR / "pending_memory_queue.json"

PENDING_DIR.mkdir(
    parents=True,
    exist_ok=True
)

# ============================================================
# ENV
# ============================================================

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

# ============================================================
# SUPABASE
# ============================================================

from supabase import create_client

SUPABASE_URL = os.getenv(
    "SUPABASE_URL"
)

SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or
    os.getenv("SUPABASE_KEY")
)

if not SUPABASE_URL or not SUPABASE_KEY:

    raise Exception(
        "Missing Supabase credentials"
    )

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

# ============================================================
# PULL RAW_CATCHALL
# ============================================================

print("\n=== PULLING RAW_CATCHALL ===")

all_rows = []

page_size = 1000
start = 0

while True:

    response = (
        supabase
        .table("raw_catchall")
        .select("*")
        .range(start, start + page_size - 1)
        .execute()
    )

    batch = response.data or []

    print(
        f"Batch {start}: {len(batch)}"
    )

    if not batch:
        break

    all_rows.extend(batch)

    if len(batch) < page_size:
        break

    start += page_size

rows = all_rows

print(
    f"Rows Pulled: {len(rows)}"
)

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

        "timestamp": row.get(
            "created_at"
        ),

        "session_id": row.get(
            "session_id"
        ),

        "role": row.get(
            "role"
        ),

        "source": "raw_catchall"
    })

# ============================================================
# SAVE QUEUE
# ============================================================

with open(
    QUEUE_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        memories,
        f,
        indent=2,
        ensure_ascii=False
    )

print(
    f"Queue Saved: {QUEUE_FILE}"
)

print(
    f"Memories Saved: {len(memories)}"
)

print("\n=== COMPLETE ===")

