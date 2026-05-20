# =====================================================
# AODS — ENGINE.PY PROPER INSTALL + TEST
# PURPOSE:
# Install the Python bridge correctly into:
#
# C:\Shine_L\memory\sync\engine.py
#
# Then test the cognition bridge safely.
# =====================================================

cd C:\Shine_L

# =====================================================
# STEP 1 — OPEN ENGINE FILE
# =====================================================

notepad .\memory\sync\engine.py

# =====================================================
# STEP 2 — DELETE EVERYTHING
# =====================================================

# DELETE ALL EXISTING CONTENT
# inside engine.py

# =====================================================
# STEP 3 — PASTE THIS FULL PYTHON CODE
# =====================================================

from supabase import create_client
from dotenv import load_dotenv
from pathlib import Path
import os
import json
from datetime import datetime

# =====================================================
# RUNTIME SYNC
# =====================================================

def run_sync():

    # ============================================
    # LOAD ENV
    # ============================================

    ROOT = Path("C:/Shine_L")

    load_dotenv(ROOT / ".env")

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

    if not SUPABASE_URL or not SUPABASE_KEY:

        print("ERROR: Missing Supabase credentials")

        return

    # ============================================
    # CONNECT
    # ============================================

    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

    # ============================================
    # PATHS
    # ============================================

    pending_path = (
        ROOT
        / "memory"
        / "pending"
        / "pending_memory_queue.json"
    )

    if not pending_path.exists():

        pending_path.write_text(
            "[]",
            encoding="utf-8"
        )

    # ============================================
    # LOAD EXISTING MEMORY
    # ============================================

    try:

        existing = json.loads(
            pending_path.read_text(
                encoding="utf-8"
            )
        )

    except:

        existing = []

    existing_ids = set()

    for item in existing:

        if "id" in item:

            existing_ids.add(
                item["id"]
            )

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

    print(f"ROWS RETURNED: {len(rows)}")

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
            json.dumps(
                existing,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        print(
            f"SUCCESS: Added {len(new_rows)} new memories."
        )

    else:

        print("No new memories found.")

    print(
        f"Total pending memories: {len(existing)}"
    )

    print("Memory ingestion complete.")

# =====================================================
# DIRECT EXECUTION SUPPORT
# =====================================================

if name == "main":

    run_sync()

# =====================================================
# STEP 4 — SAVE FILE
# =====================================================

# Press:
#
# CTRL + S

# =====================================================
# STEP 5 — TEST ENGINE DIRECTLY
# =====================================================

python .\memory\sync\engine.py

# =====================================================
# EXPECTED SUCCESS
# =====================================================

# Terminal should show:
#
# Pulling memories from Supabase...
# ROWS RETURNED: XXX
# SUCCESS: Added XXX new memories.
# Memory ingestion complete.

# =====================================================
# STEP 6 — VERIFY
# =====================================================

# Open:
#
# C:\Shine_L\memory\pending\pending_memory_queue.json
#
# Expected:
#
# - NOT []
# - contains memory rows
# - ids/content visible

# =====================================================
# STEP 7 — ONLY AFTER SUCCESS
# =====================================================

# THEN wire into server.py:
#
# from memory.sync.engine import run_sync
#
# and:
#
# run_sync()

# =====================================================
# IMPORTANT
# =====================================================

# Python code goes INSIDE:
#
# engine.py
#
# NOT into PowerShell directly.
#
# Only this line goes into terminal:
#
# python .\memory\sync\engine.py
#
# =====================================================