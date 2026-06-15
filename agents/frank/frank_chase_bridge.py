# =====================================================
# FRANK -> CHASE BRIDGE
# RAT PACK
# AODS 6
# =====================================================

from agents.chase.chase import (
    run_chase_checker
)


# =====================================================
# BRIDGE
# =====================================================

def run_frank_chase_bridge(
    frank_output
):

    lesson = ""

    lessons = (
        frank_output.get(
            "lessons",
            []
        )
        or
        []
    )

    if lessons:

        lesson = (
            " ".join(
                str(x)
                for x in lessons
            )
        )

    if not lesson:

        lesson = (
            frank_output.get(
                "summary",
                ""
            )
        )

    chase_packet = {

        "lesson":
            lesson

    }

    chase_result = (
        run_chase_checker(
            chase_packet
        )
    )

    return {

        "agent":
            "Frank Chase Bridge",

        "lesson":
            lesson,

        "chase_result":
            chase_result

    }


# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    sample = {

        "summary":
            "External certainty appears repeatedly.",

        "lessons": [

            "External certainty is being sought during uncertainty."

        ]

    }

    result = (
        run_frank_chase_bridge(
            sample
        )
    )

    import json

    print(
        json.dumps(
            result,
            indent=2
        )
    )
