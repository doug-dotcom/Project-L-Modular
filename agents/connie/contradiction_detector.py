# =====================================================
# CONTRADICTION DETECTOR
# TIER 1 - AODS 13
# =====================================================

from typing import List, Dict


POSITIVE_WORDS = {

    "improves",
    "helps",
    "supports",
    "reduces",
    "benefits",
    "effective"

}

NEGATIVE_WORDS = {

    "worsens",
    "harms",
    "increases",
    "ineffective",
    "fails",
    "damages"

}


def detect_contradictions(
    findings: List[str]
) -> Dict:

    contradictions = []

    findings = findings or []

    for i in range(len(findings)):

        left = findings[i].lower()

        for j in range(i + 1, len(findings)):

            right = findings[j].lower()

            left_positive = any(
                word in left
                for word in POSITIVE_WORDS
            )

            right_negative = any(
                word in right
                for word in NEGATIVE_WORDS
            )

            left_negative = any(
                word in left
                for word in NEGATIVE_WORDS
            )

            right_positive = any(
                word in right
                for word in POSITIVE_WORDS
            )

            if (
                left_positive and right_negative
            ) or (
                left_negative and right_positive
            ):

                contradictions.append({

                    "finding_1": findings[i],

                    "finding_2": findings[j]

                })

    return {

        "agent":
            "Contradiction Detector",

        "contradiction_count":
            len(contradictions),

        "contradictions":
            contradictions

    }


if __name__ == "__main__":

    sample = [

        "Exercise improves cognition",

        "Exercise worsens cognition",

        "Sleep improves memory"

    ]

    result = detect_contradictions(
        sample
    )

    print(result)

    assert result["contradiction_count"] == 1

