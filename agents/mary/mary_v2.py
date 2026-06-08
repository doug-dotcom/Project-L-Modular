import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")

SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    or
    os.getenv("SUPABASE_KEY", "")
)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

TABLES = [

    "memory_family",
    "memory_identity",
    "memory_recovery",
    "memory_relationships",
    "memory_project_l",
    "memory_health",
    "memory_sport",
    "memory_work"

]

SUBJECT_MAP = {

    "iyla": "Iyla",
    "ashton": "Ashton",
    "luella": "Luella",
    "mehlia": "Mehlia",

    "cass": "Cass",
    "leah": "Leah",
    "tamara": "Tamara",

    "doug": "Doug",
    "dougie": "Doug",

    "project l": "Project L",
    "brains trust": "Project L"

}

def extract_subjects(content):

    text = str(content).lower()

    subjects = []

    for keyword, subject in SUBJECT_MAP.items():

        if keyword in text:
            subjects.append(subject)

    subjects = list(
        dict.fromkeys(subjects)
    )

    primary_subject = None

    if subjects:
        primary_subject = subjects[0]

    return {
        "primary_subject": primary_subject,
        "subjects": subjects
    }

def process_table(table):

    rows = (
        supabase.table(table)
        .select("*")
        .execute()
    ).data or []

    updated = 0
    subjects_found = 0

    for row in rows:

        content = row.get(
            "content",
            ""
        )

        subject_data = extract_subjects(
            content
        )

        if subject_data["primary_subject"]:
            subjects_found += 1

        processed = (
            row.get(
                "processed_by",
                []
            )
            or
            []
        )

        if "mary_v2" not in processed:
            processed.append(
                "mary_v2"
            )

        (
            supabase.table(table)
            .update({

                "primary_subject":
                    subject_data[
                        "primary_subject"
                    ],

                "subjects":
                    subject_data[
                        "subjects"
                    ],

                "processed_by":
                    processed

            })
            .eq(
                "id",
                row["id"]
            )
            .execute()
        )

        updated += 1

    return {
        "updated": updated,
        "subjects_found": subjects_found
    }

def run():

    total_updated = 0
    total_subjects = 0

    print()
    print("=" * 40)
    print("OPERATION MARY V2")
    print("=" * 40)

    for table in TABLES:

        result = process_table(
            table
        )

        print(
            f"{table} | updated={result['updated']} | subjects={result['subjects_found']}"
        )

        total_updated += result[
            "updated"
        ]

        total_subjects += result[
            "subjects_found"
        ]

    print()
    print("=" * 40)
    print("OUTCOME")
    print("=" * 40)

    print(
        f"Rows Updated: {total_updated}"
    )

    print(
        f"Subjects Found: {total_subjects}"
    )

if __name__ == "__main__":

    run()
