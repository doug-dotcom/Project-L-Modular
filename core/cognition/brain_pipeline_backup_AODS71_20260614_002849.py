import os
import sys

from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from supabase import create_client

from agents.coach.mary_coach_adapter import (
    run_memory_to_coach
)

load_dotenv(ROOT / ".env")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    or os.getenv("SUPABASE_KEY", "")
)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

RAW_TABLE = "raw_catchall"

MEMORY_TABLES = [
    "memory_family",
    "memory_identity",
    "memory_recovery",
    "memory_relationships",
    "memory_project_l",
    "memory_health",
    "memory_sport",
    "memory_work",
    "memory_general",
]

ENTITY_TABLE_MAP = {
    "iyla": "memory_family",
    "ashton": "memory_family",
    "luella": "memory_family",
    "mehlia": "memory_family",

    "cass": "memory_relationships",
    "leah": "memory_relationships",
    "tamara": "memory_relationships",

    "project l": "memory_project_l",
    "mary": "memory_project_l",
    "carol": "memory_project_l",
    "sara": "memory_project_l",
    "izzy": "memory_project_l",
    "rachel": "memory_project_l",
    "ellie": "memory_project_l",
    "desley": "memory_project_l",

    "recovery": "memory_recovery",
    "aa": "memory_recovery",
    "na": "memory_recovery",
    "pauline": "memory_recovery",

    "health": "memory_health",
    "sleep": "memory_health",
    "weight": "memory_health",

    "hockey": "memory_sport",
    "sport": "memory_sport",
}


VALUE_KEYWORDS = {
    "family": "Family",
    "kids": "Family",
    "children": "Family",
    "truth": "Truth",
    "recovery": "Recovery",
    "help": "Service",
    "service": "Service",
    "love": "Love",
    "safe": "Safety",
    "safety": "Safety",
    "project l": "Project L",
}


def clean_content(text):
    return str(text or "").strip()


def detect_target_table(content):
    text = content.lower()

    for keyword, table in ENTITY_TABLE_MAP.items():
        if keyword in text:
            return table

    return "memory_general"


def extract_subjects(content):
    text = content.lower()
    subjects = []

    for keyword in ENTITY_TABLE_MAP.keys():
        if keyword in text:
            subjects.append(keyword.title())

    return list(dict.fromkeys(subjects))


def extract_values(content):
    text = content.lower()
    values = []

    for keyword, value in VALUE_KEYWORDS.items():
        if keyword in text:
            values.append(value)

    return list(dict.fromkeys(values))


def calculate_salience(content):
    text = content.lower()

    score = 50

    high_signal_words = [
        "important",
        "breakthrough",
        "remember",
        "save",
        "love",
        "family",
        "recovery",
        "project l",
        "pauline",
        "truth",
        "identity",
    ]

    for word in high_signal_words:
        if word in text:
            score += 8

    if len(content) > 500:
        score += 10

    return min(score, 100)


def calculate_importance(content):
    text = content.lower()

    score = 50

    if "save" in text:
        score += 20

    if "breakthrough" in text:
        score += 20

    if "family" in text or "kids" in text:
        score += 15

    if "project l" in text:
        score += 15

    if "recovery" in text:
        score += 15

    return min(score, 100)


def already_processed(table, raw_id):
    result = (
        supabase.table(table)
        .select("id")
        .eq("raw_id", raw_id)
        .limit(1)
        .execute()
    )

    return bool(result.data)


def process_raw_memory(row):
    raw_id = row.get("id")
    content = clean_content(row.get("content", ""))

    if not content:
        return None

    target_table = detect_target_table(content)

    if already_processed(target_table, raw_id):
        return {
            "raw_id": raw_id,
            "status": "skipped",
            "reason": "already_processed",
            "target": target_table,
        }

    subjects = extract_subjects(content)
    values = extract_values(content)

    salience = calculate_salience(content)
    importance = calculate_importance(content)

    anchor = importance >= 80 or salience >= 80

    payload = {
        "raw_id": raw_id,
        "content": content,

        "primary_subject": subjects[0] if subjects else None,
        "subjects": subjects,

        "importance": importance,
        "salience": salience,
        "anchor": anchor,

        "values": values,
        "preferences": [],

        "relationships": [],
        "metadata": {
            "source_table": RAW_TABLE,
            "processed_at": datetime.now().isoformat(),
            "pipeline": "brain_pipeline_v1",
        },

        "processed_by": [
            "carol",
            "sara",
            "mary",
            "izzy",
        ],
    }

    supabase.table(target_table).insert(payload).execute()

    # =====================================================
    # AUTOMATIC COACH TRIGGER
    # =====================================================

    try:

        memory_result = (
            supabase.table(target_table)
            .select("*")
            .eq("raw_id", raw_id)
            .limit(1)
            .execute()
        )

        memories = memory_result.data or []

        if memories:

            run_memory_to_coach(
                memories[0]
            )

            print(
                f"COACH TRIGGERED -> {raw_id}"
            )

    except Exception as e:

        print(
            f"COACH TRIGGER ERROR: {e}"
        )

    return {
        "raw_id": raw_id,
        "status": "processed",
        "target": target_table,
        "subjects": subjects,
        "values": values,
        "importance": importance,
        "salience": salience,
        "anchor": anchor,
    }


def run(limit=2500):
    result = (
        supabase.table(RAW_TABLE)
        .select("*")
        .order("id", desc=True)
        .limit(limit)
        .execute()
    )

    rows = result.data or []
    rows.reverse()

    outcomes = []

    for row in rows:
        try:
            outcome = process_raw_memory(row)
            if outcome:
                outcomes.append(outcome)
        except Exception as e:
            outcomes.append({
                "raw_id": row.get("id"),
                "status": "error",
                "error": str(e),
            })

    return {
        "status": "ok",
        "checked": len(rows),
        "outcomes": outcomes,
    }


if __name__ == "__main__":
    result = run(limit=2500)

    print()
    print("=" * 50)
    print("PROJECT L BRAIN PIPELINE V1")
    print("=" * 50)
    print("Checked:", result["checked"])

    for item in result["outcomes"]:
        print(item)





