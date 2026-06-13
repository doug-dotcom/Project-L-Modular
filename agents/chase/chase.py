# =====================================================
# AODS 3 - CHASE CHECKER
# THE LEARNING LOOPERS
# =====================================================

from datetime import datetime


def run_chase_checker(finlay_output):

    lesson = finlay_output.get(
        "lesson",
        ""
    )

    evidence = []

    confidence = 50

    lower = lesson.lower()

    if "certainty" in lower:
        evidence.append(
            "Repeated validation seeking observed"
        )
        evidence.append(
            "Mentor pattern previously detected"
        )
        confidence += 25

    if "agency" in lower:
        evidence.append(
            "Keys metaphor repeatedly present"
        )
        confidence += 15

    if "protection" in lower:
        evidence.append(
            "Recurring protector pattern detected"
        )
        confidence += 15

    result = {

        "agent":
            "Chase Checker",

        "team":
            "Learning Loopers",

        "aods":
            "AODS 3",

        "role":
            "Reality Checker",

        "timestamp":
            datetime.now().isoformat(),

        "lesson":
            lesson,

        "evidence":
            evidence,

        "validated":
            confidence >= 70,

        "confidence":
            min(confidence, 100),

        "next_agent":
            "Mannie Mapper"

    }

    return result


if __name__ == "__main__":

    sample_input = {

        "lesson":
            "External certainty is being sought during uncertainty."

    }

    output = run_chase_checker(
        sample_input
    )

    import json

    print(
        json.dumps(
            output,
            indent=2
        )
    )
