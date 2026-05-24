import os
import json

from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

from supabase import create_client

# =====================================================
# ROOT
# =====================================================

ROOT = Path(__file__).resolve().parents[2]

DOMAIN_DIR = ROOT / "memory" / "domains"

# =====================================================
# SUPABASE
# =====================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# =====================================================
# DOMAIN MAP
# =====================================================

DOMAIN_MAP = {

    "short_term_family": "family.json",

    "short_term_finance": "finance.json",

    "short_term_general": "general.json",

    "short_term_health": "health.json",

    "short_term_identity": "identity.json",

    "short_term_knowledge": "knowledge.json",

    "short_term_project_l": "project_l.json",

    "short_term_relationships": "relationships.json",

    "short_term_sport": "sport.json",

    "short_term_work": "work.json"
}

# =====================================================
# LOG
# =====================================================

def log(msg):

    print(
        f"{datetime.now().isoformat()} | {msg}"
    )

# =====================================================
# LOAD JSON
# =====================================================

def load_json(path):

    if not path.exists():
        return []

    try:

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

            if isinstance(data, list):
                return data

            return []

    except Exception as e:

        log(f"LOAD ERROR {path.name}: {e}")

        return []

# =====================================================
# SAVE JSON
# =====================================================

def save_json(path, data):

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )

# =====================================================
# GET IDS
# =====================================================

def get_existing_ids(data):

    ids = set()

    for item in data:

        if not isinstance(item, dict):
            continue

        item_id = item.get("id")

        if item_id:
            ids.add(str(item_id))

    return ids

# =====================================================
# MAIN SYNC
# =====================================================

def run_sync():

    if not SUPABASE_URL or not SUPABASE_KEY:

        log("SUPABASE ENV MISSING")

        return

    supabase = create_client(
        SUPABASE_URL,
        SUPABASE_KEY
    )

    log("SUPABASE CONNECTED")

    DOMAIN_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # =================================================
    # LOOP DOMAINS
    # =================================================

    for table_name, json_name in DOMAIN_MAP.items():

        try:

            log(f"SYNCING {table_name}")

            result = (
                supabase
                .table(table_name)
                .select("*")
                .order("created_at", desc=False)
                .execute()
            )

            rows = result.data or []

            if not isinstance(rows, list):

                log(
                    f"SKIPPED invalid rows in {table_name}"
                )

                continue

            json_path = DOMAIN_DIR / json_name

            existing = load_json(json_path)

            existing_ids = get_existing_ids(existing)

            added = 0

            for row in rows:

                if not isinstance(row, dict):

                    log(
                        f"SKIPPED malformed row in {table_name}"
                    )

                    continue

                row_id = str(
                    row.get("id", "")
                )

                if not row_id:
                    continue

                if row_id in existing_ids:
                    continue

                existing.append(row)

                existing_ids.add(row_id)

                added += 1

            save_json(
                json_path,
                existing
            )

            log(
                f"{json_name} -> +{added} memories"
            )

        except Exception as e:

            log(
                f"FAILED {table_name}: {e}"
            )

    log("DOMAIN SYNC COMPLETE")

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":

    run_sync()