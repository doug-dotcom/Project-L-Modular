from pathlib import Path
import re

target = Path(r"C:\Shine_L\api\server.py")
text = target.read_text(encoding="utf-8")

# -----------------------------------------------------
# 1. ADD SAFE BRAIN PIPELINE IMPORT
# -----------------------------------------------------

needle = """from agents.tegan.tegan import (
    route_message
)

try:
"""

replacement = """from agents.tegan.tegan import (
    route_message
)

try:
    from core.cognition.brain_pipeline import (
        process_raw_memory
    )
except Exception as e:
    process_raw_memory = None

try:
"""

text = text.replace(needle, replacement)

# -----------------------------------------------------
# 2. REPLACE write_raw_catchall SO IT RETURNS INSERTED ROW
# -----------------------------------------------------

pattern = r"""def write_raw_catchall\(role, content, source="chat"\):.*?# =====================================================
# SHORT TERM MEMORY
# ====================================================="""

new_block = '''def write_raw_catchall(role, content, source="chat"):
    try:
        if not supabase:
            log("SUPABASE NOT CONNECTED")
            return False

        payload = {
            "role": str(role),
            "source": str(source),
            "content": str(content),
            "metadata": {}
        }

        result = (
            supabase.table("raw_catchall")
            .insert(payload)
            .execute()
        )

        rows = result.data or []

        log(f"RAW MEMORY SAVED: {role}")

        if rows:
            return rows[0]

        return True

    except Exception as e:
        log(f"RAW MEMORY ERROR: {e}")
        return False


def run_auto_brain_pipeline(raw_row):
    try:
        if not process_raw_memory:
            log("AUTO BRAIN SKIPPED: brain_pipeline unavailable")
            return False

        if not raw_row or not isinstance(raw_row, dict):
            log("AUTO BRAIN SKIPPED: no raw row returned")
            return False

        outcome = process_raw_memory(raw_row)

        log(f"AUTO BRAIN OUTCOME: {outcome}")

        return outcome

    except Exception as e:
        log(f"AUTO BRAIN ERROR: {e}")
        return False

# =====================================================
# SHORT TERM MEMORY
# ====================================================='''

text = re.sub(pattern, new_block, text, flags=re.S)

# -----------------------------------------------------
# 3. PATCH USER RAW SAVE
# -----------------------------------------------------

old_user = '''    write_raw_catchall(
        "user",
        user_message
    )'''

new_user = '''    raw_user_row = write_raw_catchall(
        "user",
        user_message
    )

    run_auto_brain_pipeline(
        raw_user_row
    )'''

text = text.replace(old_user, new_user)

# -----------------------------------------------------
# 4. PATCH ASSISTANT RAW SAVE
# -----------------------------------------------------

old_assistant = '''    write_raw_catchall(
        "assistant",
        reply
    )'''

new_assistant = '''    raw_assistant_row = write_raw_catchall(
        "assistant",
        reply
    )

    run_auto_brain_pipeline(
        raw_assistant_row
    )'''

text = text.replace(old_assistant, new_assistant)

target.write_text(text, encoding="utf-8")
print("AODS 5 PATCH APPLIED")
