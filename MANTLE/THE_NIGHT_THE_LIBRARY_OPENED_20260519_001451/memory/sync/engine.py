# ============================================================
# MEMORY SYNC ENGINE
# AODS-93
# ============================================================

import json
from pathlib import Path

from supabase import create_client

ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

IDENTITY_FILE = (
    ROOT
    / "memory"
    / "identity.json"
)

def build_supabase():

    try:

        import os

        url = os.getenv(
            "SUPABASE_URL",
            ""
        )

        key = os.getenv(
            "SUPABASE_KEY",
            ""
        )

        if not url or not key:
            return None

        return create_client(
            url,
            key
        )

    except Exception as e:

        print(
            "SYNC SUPABASE ERROR:",
            e
        )

        return None

def load_identity():

    try:

        if not IDENTITY_FILE.exists():
            return {}

        return json.loads(
            IDENTITY_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception as e:

        print(
            "IDENTITY LOAD ERROR:",
            e
        )

        return {}

def flatten_identity(data):

    rows = []

    try:

        for category, value in data.items():

            if isinstance(value, dict):

                for subkey, subvalue in value.items():

                    if isinstance(subvalue, list):

                        for item in subvalue:

                            rows.append({

                                "category": category,

                                "content": str(item),

                                "importance": 10
                            })

                    else:

                        rows.append({

                            "category": category,

                            "content": f"{subkey}: {subvalue}",

                            "importance": 8
                        })

    except Exception as e:

        print(
            "FLATTEN ERROR:",
            e
        )

    return rows

def sync_identity_to_supabase():

    supabase = build_supabase()

    if not supabase:
        return {
            "status": "failed",
            "reason": "no_supabase"
        }

    identity = load_identity()

    rows = flatten_identity(identity)

    synced = 0

    for row in rows:

        try:

            supabase.table(
                "memories"
            ).insert(
                row
            ).execute()

            synced += 1

        except Exception as e:

            print(
                "SYNC ROW ERROR:",
                e
            )

    return {
        "status": "online",
        "synced_rows": synced
    }

def sync_status():

    return {
        "status": "online",
        "operation": "AODS93",
        "identity_file": str(
            IDENTITY_FILE
        )
    }

