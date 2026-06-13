# =====================================================
# AODS 7 - LLGR V2
# LEARNING LOOPERS GROWTH RECORD
# =====================================================

from datetime import datetime


def create_llgr(
    reflection,
    lesson,
    validated,
    adjustment,
    agency_score,
    keys_owner,
    validation_count=1,
    confidence_score=50,
    contradiction_count=0,
    evidence=None,
    contradiction_evidence=None
):

    if evidence is None:
        evidence = []

    if contradiction_evidence is None:
        contradiction_evidence = []

    return {

        "record_type":
            "LLGR",

        "version":
            "2.0",

        "timestamp":
            datetime.now().isoformat(),

        "reflection":
            reflection,

        "lesson":
            lesson,

        "validated":
            validated,

        "validation_count":
            validation_count,

        "confidence_score":
            confidence_score,

        "contradiction_count":
            contradiction_count,

        "evidence":
            evidence,

        "contradiction_evidence":
            contradiction_evidence,

        "adjustment":
            adjustment,

        "agency_score":
            agency_score,

        "keys_owner":
            keys_owner,

        "growth_stored":
            True,

        "ian_note":
            "Growth, confidence and contradiction tracking recorded."

    }


if __name__ == "__main__":

    record = create_llgr(

        reflection=
            "Negative thought detected: I suck at hockey.",

        lesson=
            "Evidence indicates Doug is good at hockey.",

        validated=
            True,

        adjustment=
            "Reject unsupported negative thought and trust the evidence.",

        agency_score=
            82,

        keys_owner=
            "Doug",

        validation_count=
            56,

        confidence_score=
            82,

        contradiction_count=
            1,

        evidence=[
            "56 prior entries support hockey competence."
        ],

        contradiction_evidence=[
            "1 current negative thought."
        ]

    )

    import json

    print(
        json.dumps(
            record,
            indent=2
        )
    )
