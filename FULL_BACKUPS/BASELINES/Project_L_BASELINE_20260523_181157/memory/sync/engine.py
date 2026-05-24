import os
import json
import subprocess
import sys

from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from supabase import create_client

ROOT = Path(__file__).resolve().parents[2]

MEMORY_DIR = ROOT / "memory"

PENDING_DIR = MEMORY_DIR / "pending"

PENDING_FILE = (
    PENDING_DIR /
    "pending_memory_queue.json"
)

SUPABASE_URL = os.getenv(
    "SUPABASE_URL",
    ""
)

SUPABASE_KEY = os.getenv(
    "SUPABASE_KEY",
    ""
)

def log(msg):

    print(
        f"{datetime.now().isoformat()} | {msg}"
    )

def load_queue():

    if not PENDING_FILE.exists():
        return []

    try:

        with open(
            PENDING_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:

        return []

def save_queue(queue):

    PENDING_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        PENDING_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            queue,
            f,
            indent=2,
            ensure_ascii=False
        )

def get_existing_ids(queue):

    ids = set()

    for item in queue:

        raw_id = item.get("raw_id")

        if raw_id:
            ids.add(str(raw_id))

    return ids

def pull_raw_catchall(limit=1000):

    if not SUPABASE_URL or not SUPABASE_KEY:

        log("SUPABASE ENV MISSING")

        return []

    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

    log("SUPABASE CONNECTED")

    log("Pulling memories from Supabase...")

    result = (
        supabase
        .table("raw_catchall")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    rows = result.data or []

    log(
        f"ROWS RETURNED: {len(rows)}"
    )

    return rows

def convert_raw_to_pending(row):

    return {
        "raw_id": str(
            row.get("id", "")
        ),

        "created_at": row.get(
            "created_at",
            datetime.now().isoformat()
        ),

        "role": row.get(
            "role",
            ""
        ),

        "source": row.get(
            "source",
            "raw_catchall"
        ),

        "content": row.get(
            "content",
            ""
        ),

        "metadata": row.get(
            "metadata",
            {}
        ),

        "status": "pending",

        "added_at": datetime.now().isoformat()
    }

def run_script(script_path):

    if not script_path.exists():

        log(
            f"SKIPPED missing script: {script_path}"
        )

        return False

    log(
        f"RUNNING: {script_path.name}"
    )

    try:

        result = subprocess.run(
            [
                sys.executable,
                str(script_path)
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True
        )

        if result.stdout:
            print(result.stdout)

        if result.stderr:
            print(result.stderr)

        if result.returncode == 0:

            log(
                f"SUCCESS: {script_path.name}"
            )

            return True

        log(
            f"FAILED: {script_path.name}"
        )

        return False

    except Exception as e:

        log(
            f"ERROR running {script_path.name}: {e}"
        )

        return False

def run_sync(limit=100):

    queue = load_queue()

    existing_ids = get_existing_ids(queue)

    rows = pull_raw_catchall(limit=limit)

    added = 0

    for row in rows:

        raw_id = str(
            row.get("id", "")
        )

        if not raw_id:
            continue

        if raw_id in existing_ids:
            continue

        content = str(
            row.get("content", "")
        ).strip()

        if not content:
            continue

        queue.append(
            convert_raw_to_pending(row)
        )

        existing_ids.add(raw_id)

        added += 1

    save_queue(queue)

    log(
        f"SUCCESS: Added {added} new memories."
    )

    log(
        f"Total pending memories: {len(queue)}"
    )

    scripts = [

        MEMORY_DIR / "memory_classifier.py",

        MEMORY_DIR / "memory_compression.py",

        MEMORY_DIR / "domain_updater.py",

        MEMORY_DIR / "memory_reinforcement.py"
    ]

    for script in scripts:

        run_script(script)

    log("Memory ingestion complete.")

    return {
        "success": True,
        "added": added,
        "pending_total": len(queue)
    }

if __name__ == "__main__":

    run_sync()
