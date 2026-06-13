import os
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import os

from dotenv import load_dotenv
from supabase import create_client

# =====================================================
# ENV
# =====================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")

SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_KEY")
)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

# =====================================================
# RETRIEVE
# =====================================================

def retrieve_growth_context(limit=10):

    result = (
        supabase
        .table("allegra_history")
        .select("*")
        .order(
            "stored_at",
            desc=True
        )
        .limit(limit)
        .execute()
    )

    rows = result.data or []

    lessons = []

    for row in rows:

        llgr = row.get(
            "llgr",
            {}
        )

        lesson = llgr.get(
            "lesson"
        )

        if lesson:

            lessons.append(
                lesson
            )

    return lessons

# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    lessons = retrieve_growth_context()

    print()
    print("=" * 50)
    print("ALLEGRA RETRIEVAL")
    print("=" * 50)

    for lesson in lessons:

        print(
            f"• {lesson}"
        )

    print()
    print("=" * 50)
    print("AODS 13.0 COMPLETE")
    print("=" * 50)


