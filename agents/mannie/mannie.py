# =====================================================
# AODS 4 - MANNIE MAPPER
# THE LEARNING LOOPERS
# =====================================================

from datetime import datetime


def run_mannie_mapper(chase_output):

    lesson = chase_output.get(
        "lesson",
        ""
    )

    adjustment = (
        "Continue observing."
    )

    lower = lesson.lower()

    if "external certainty" in lower:

        adjustment = (
            "Notice validation seeking sooner."
        )

    elif "authority" in lower:

        adjustment = (
            "Pause before asking others for certainty."
        )

    elif "agency" in lower:

        adjustment = (
            "Keep ownership of decisions."
        )

    elif "protection" in lower:

        adjustment = (
            "Protect without taking control."
        )

    result = {

        "agent":
            "Mannie Mapper",

        "team":
            "Learning Loopers",

        "aods":
            "AODS 4",

        "role":
            "Adjustment Mapper",

        "timestamp":
            datetime.now().isoformat(),

        "lesson":
            lesson,

        "adjustment":
            adjustment,

        "adjustment_size":
            "small",

        "next_agent":
            "Gary Guardian"

    }

    return result


if __name__ == "__main__":

    sample_input = {

        "lesson":
            "External certainty is being sought during uncertainty."

    }

    output = run_mannie_mapper(
        sample_input
    )

    import json

    print(
        json.dumps(
            output,
            indent=2
        )
    )
