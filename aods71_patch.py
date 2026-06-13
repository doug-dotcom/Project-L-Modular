from pathlib import Path

target = Path(r"C:\Shine_L\core\cognition\brain_pipeline.py")

text = target.read_text(
    encoding="utf-8"
)

old = """
        if memories:

            run_memory_to_coach(
                memories[0]
            )

            print(
                f"COACH TRIGGERED -> {raw_id}"
            )
"""

new = """
        if memories:

            coach_result = run_memory_to_coach(
                memories[0]
            )

            supabase.table(
                target_table
            ).update(
                {
                    "ronnie":
                        coach_result.get(
                            "ronnie"
                        ),

                    "finlay":
                        coach_result.get(
                            "finlay"
                        ),

                    "chase":
                        coach_result.get(
                            "chase"
                        ),

                    "mannie":
                        coach_result.get(
                            "mannie"
                        ),

                    "gary":
                        coach_result.get(
                            "gary"
                        ),

                    "ian":
                        coach_result.get(
                            "ian"
                        ),

                    "llgr":
                        coach_result.get(
                            "llgr"
                        )
                }
            ).eq(
                "raw_id",
                raw_id
            ).execute()

            print(
                f"COACH STORED -> {raw_id}"
            )
"""

text = text.replace(
    old,
    new
)

target.write_text(
    text,
    encoding="utf-8"
)

print(
    "AODS 7.1 PATCH APPLIED"
)
