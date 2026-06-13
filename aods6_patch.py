from pathlib import Path

target = Path(r"C:\Shine_L\core\cognition\brain_pipeline.py")

text = target.read_text(encoding="utf-8")

old = """
    supabase.table(target_table).insert(payload).execute()

    return {
"""

new = """
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
"""

text = text.replace(old, new)

target.write_text(
    text,
    encoding="utf-8"
)

print("AODS 6 PATCH APPLIED")
