from supabase import create_client
from dotenv import load_dotenv
from pathlib import Path
import os
import json

# =====================================================
# ROOT
# =====================================================

ROOT = Path("C:/Shine_L")

# =====================================================
# LOAD ENV
# =====================================================

load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# =====================================================
# MAIN SYNC FUNCTION
# =====================================================

def run_sync():

    try:

        # =================================================
        # VALIDATE ENV
        # =================================================

        if not SUPABASE_URL or not SUPABASE_KEY:

            print("ERROR: Missing Supabase credentials")

            return False

        # =================================================
        # CONNECT
        # =================================================

        supabase = create_client(
            SUPABASE_URL,
            SUPABASE_KEY
        )

        print("SUPABASE CONNECTED")

        # =================================================
        # PENDING PATH
        # =================================================

        pending_path = (
            ROOT
            / "memory"
            / "pending"
            / "pending_memory_queue.json"
        )

        pending_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        # =================================================
        # CREATE FILE IF MISSING
        # =================================================

        if not pending_path.exists():

            pending_path.write_text(
                "[]",
                encoding="utf-8"
            )

        # =================================================
        # LOAD EXISTING
        # =================================================

        try:

            existing = json.loads(
                pending_path.read_text(
                    encoding="utf-8"
                )
            )

            if not isinstance(existing, list):
                existing = []

        except Exception:

            existing = []

        existing_ids = set()

        for item in existing:

            try:

                if "id" in item:

                    existing_ids.add(
                        item["id"]
                    )

            except Exception:
                pass

        # =================================================
        # PULL SUPABASE MEMORY
        # =================================================

        print("Pulling memories from Supabase...")

        response = (
            supabase
            .table("raw_catchall")
            .select("*")
            .order("created_at")
            .execute()
        )

        rows = response.data or []

        print(f"ROWS RETURNED: {len(rows)}")

        # =================================================
        # FILTER NEW ROWS
        # =================================================

        new_rows = []

        for row in rows:

            try:

                row_id = row.get("id")

                if row_id not in existing_ids:

                    new_rows.append(row)

            except Exception as e:

                print(f"ROW PROCESS ERROR: {e}")

        # =================================================
        # APPEND NEW ROWS
        # =================================================

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

        return True

    except Exception as e:

        import traceback

        print(f"SYNC ERROR: {e}")

        print(traceback.format_exc())

        return False

# =====================================================
# DIRECT EXECUTION
# =====================================================

if __name__ == "__main__":

    run_sync()