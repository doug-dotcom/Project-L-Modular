# =====================================================
# AODS 6.1 - IAN V2
# CONFIDENCE & BELIEF TRACKING
# =====================================================

from datetime import datetime


def calculate_confidence(
    validation_count,
    contradiction_count
):

    total = (
        validation_count +
        contradiction_count
    )

    if total == 0:
        return 50

    score = (
        validation_count /
        total
    ) * 100

    return round(score, 2)


def run_ian_integration(
    gary_output,

    validation_count=1,

    contradiction_count=0,

    supporting_evidence=None,

    contradicting_evidence=None
):

    if supporting_evidence is None:
        supporting_evidence = []

    if contradicting_evidence is None:
        contradicting_evidence = []

    adjustment = gary_output.get(
        "adjustment",
        ""
    )

    agency_score = gary_output.get(
        "agency_score",
        0
    )

    confidence_score = calculate_confidence(

        validation_count,

        contradiction_count

    )

    growth_record = {

        "agent":
            "Ian Weiner",

        "team":
            "Learning Loopers",

        "aods":
            "AODS 6.1",

        "role":
            "Confidence & Integration Keeper",

        "timestamp":
            datetime.now().isoformat(),

        "what_changed":
            adjustment,

        "agency_score":
            agency_score,

        "validation_count":
            validation_count,

        "contradiction_count":
            contradiction_count,

        "confidence_score":
            confidence_score,

        "supporting_evidence":
            supporting_evidence,

        "contradicting_evidence":
            contradicting_evidence,

        "identity_shift":
            "Growth Detected",

        "transformation_detected":
            True,

        "growth_stored":
            True

    }

    return growth_record


if __name__ == "__main__":

    sample_input = {

        "adjustment":
            "Notice validation seeking sooner.",

        "agency_score":
            70

    }

    output = run_ian_integration(

        sample_input,

        validation_count=56,

        contradiction_count=1,

        supporting_evidence=[

            "56 prior entries support hockey competence."

        ],

        contradicting_evidence=[

            "1 negative thought."

        ]

    )

    import json

    print(
        json.dumps(
            output,
            indent=2
        )
    )
