# =====================================================
# AODS 16
# ALLEGRA PATTERN EVOLUTION
# =====================================================

import os

from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")

SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or
    os.getenv("SUPABASE_KEY")
)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

# =====================================================
# TREND
# =====================================================

def calculate_confidence(occurrences):

    return min(
        occurrences * 10,
        100
    )


def calculate_trend(occurrences):

    if occurrences <= 1:
        return "emerging"

    if occurrences <= 3:
        return "strengthening"

    if occurrences <= 9:
        return "established"

    return "deeply_reinforced"

# =====================================================
# STORE LLGR
# =====================================================

def store_llgr(llgr):

    lesson = llgr.get("lesson")

    if not lesson:
        return False

    rows = (
        supabase
        .table("allegra_history")
        .select("*")
        .execute()
        .data
    )

    for row in rows:

        existing = row.get("llgr", {})

        if existing.get("lesson") == lesson:

            occurrences = int(
                existing.get(
                    "occurrences",
                    1
                )
            ) + 1

            existing["occurrences"] = occurrences
            existing["confidence"] = calculate_confidence(occurrences)
            existing["trend"] = calculate_trend(occurrences)

            (
                supabase
                .table("allegra_history")
                .update(
                    {
                        "llgr":
                            existing
                    }
                )
                .eq(
                    "id",
                    row["id"]
                )
                .execute()
            )

            return True

    llgr["occurrences"] = 1
    llgr["confidence"] = calculate_confidence(1)
    llgr["trend"] = calculate_trend(1)

    (
        supabase
        .table("allegra_history")
        .insert(
            {
                "llgr":
                    llgr
            }
        )
        .execute()
    )

    return True

# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    test = {
        "lesson": "Trust your own judgement.",
        "agency_score": 85
    }

    store_llgr(test)

    print()
    print("=" * 50)
    print("AODS 16 COMPLETE")
    print("PATTERN EVOLUTION ACTIVE")
    print("=" * 50)

