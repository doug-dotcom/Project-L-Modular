# =====================================================
# CONFIDENCE WEIGHTING
# TIER 1 - AODS 6
# =====================================================

from typing import Dict


def calculate_confidence(
    evidence_count: int,
    source_count: int,
    contradiction_count: int = 0
) -> Dict:

    score = 50

    score += evidence_count * 5

    score += source_count * 10

    score -= contradiction_count * 15

    score = max(
        0,
        min(
            100,
            score
        )
    )

    return {

        "agent": "Confidence Weighting",

        "confidence_score": score,

        "confidence_level":

            "high"
            if score >= 80 else

            "medium"
            if score >= 50 else

            "low"

    }


if __name__ == "__main__":

    result = calculate_confidence(

        evidence_count = 5,

        source_count = 3,

        contradiction_count = 0

    )

    print(result)

    assert result["confidence_score"] == 100

    assert result["confidence_level"] == "high"

