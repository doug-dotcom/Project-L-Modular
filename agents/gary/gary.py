# =====================================================
# AODS 5 - GARY GUARDIAN
# THE LEARNING LOOPERS
# =====================================================

from datetime import datetime


def run_gary_guardian(mannie_output):

    adjustment = mannie_output.get(
        "adjustment",
        ""
    )

    lower = adjustment.lower()

    agency_score = 50

    notes = []

    if "notice" in lower:
        agency_score += 20
        notes.append(
            "Self-awareness increased."
        )

    if "ownership" in lower:
        agency_score += 20
        notes.append(
            "Ownership increased."
        )

    if "trust yourself" in lower:
        agency_score += 15
        notes.append(
            "Internal authority increased."
        )

    if "ask someone else" in lower:
        agency_score -= 20
        notes.append(
            "Potential dependency detected."
        )

    result = {

        "agent":
            "Gary Guardian",

        "team":
            "Learning Loopers",

        "aods":
            "AODS 5",

        "role":
            "Agency Guardian",

        "timestamp":
            datetime.now().isoformat(),

        "adjustment":
            adjustment,

        "agency_score":
            max(0, min(agency_score, 100)),

        "keys_owner":
            "Doug",

        "guardian_notes":
            notes,

        "approved":
            agency_score >= 60,

        "next_agent":
            "Ian Integration"

    }

    return result


if __name__ == "__main__":

    sample_input = {

        "adjustment":
            "Notice validation seeking sooner."

    }

    output = run_gary_guardian(
        sample_input
    )

    import json

    print(
        json.dumps(
            output,
            indent=2
        )
    )
