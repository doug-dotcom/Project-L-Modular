import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    or os.getenv("SUPABASE_KEY", "")
)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SOURCE_TABLE = "short_term_project_l"
TARGET_TABLE = "memory_project_l"


def clean_content(text):
    return str(text or "").strip()


def run_carol_project_l(limit=10):
    result = (
        supabase.table(SOURCE_TABLE)
        .select("*")
        .order("id", desc=True)
        .limit(limit)
        .execute()
    )

    rows = result.data or []
    rows.reverse()

    moved = 0

    for row in rows:
        content = clean_content(row.get("content", ""))

        if not content:
            continue

        payload = {
            "raw_id": row.get("id"),
            "content": content,
            "importance": 50,
            "salience": 50,
            "anchor": False,
            "processed_by": ["carol"],
            "metadata": {
                "source_table": SOURCE_TABLE,
                "carol_version": "0.1",
                "processed_at": datetime.now().isoformat()
            }
        }

        supabase.table(TARGET_TABLE).insert(payload).execute()
        moved += 1

    return {
        "status": "ok",
        "source": SOURCE_TABLE,
        "target": TARGET_TABLE,
        "moved": moved
    }


if __name__ == "__main__":
    print(run_carol_project_l())
