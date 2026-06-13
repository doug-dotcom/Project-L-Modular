# =====================================================
# AODS 2 - FINLAY FINDER
# THE LEARNING LOOPERS
# =====================================================

from datetime import datetime


def _safe_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _build_lesson(text):

    lower = text.lower()

    if "validation" in lower:
        return "External certainty is being sought during uncertainty."

    if "mentor" in lower:
        return "Trusted authority figures are influencing decision making."

    if "keys" in lower:
        return "Personal agency and ownership are central themes."

    if "protect" in lower:
        return "Protection is a recurring value."

    if "mum" in lower or "dad" in lower:
        return "Loss has influenced identity and direction."

    return "A meaningful pattern has been detected and requires further exploration."


def run_finlay_finder(reflection):

    reflection_text = ""

    if isinstance(reflection, dict):

        reflection_text += _safe_text(
            reflection.get("what_happened", "")
        )

        for item in reflection.get(
            "what_stood_out",
            []
        ):
            reflection_text += " " + item

    else:

        reflection_text = _safe_text(reflection)

    lesson = _build_lesson(
        reflection_text
    )

    result = {

        "agent":
            "Finlay Finder",

        "team":
            "Learning Loopers",

        "aods":
            "AODS 2",

        "role":
            "Lesson Finder",

        "timestamp":
            datetime.now().isoformat(),

        "lesson":
            lesson,

        "lesson_confidence":
            75,

        "next_agent":
            "Chase Checker"

    }

    return result


if __name__ == "__main__":

    sample_reflection = {

        "what_happened":
            "Doug noticed he kept looking to Pauline for validation.",

        "what_stood_out": [

            "Validation seeking was recurring.",

            "Pattern connected to mentors."

        ]

    }

    output = run_finlay_finder(
        sample_reflection
    )

    import json

    print(
        json.dumps(
            output,
            indent=2
        )
    )
