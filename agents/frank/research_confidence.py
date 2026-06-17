# =====================================================
# RESEARCH CONFIDENCE
# TIER 1 - AODS 11
# =====================================================

from typing import Dict


def calculate_research_confidence(
    source_count: int,
    agreement_count: int,
    contradiction_count: int
) -> Dict:

    score = 50

    score += source_count * 5

    score += agreement_count * 10

    score -= contradiction_count * 15

    score = max(
        0,
        min(
            100,
            score
        )
    )

    if score >= 80:
        level = "HIGH"

    elif score >= 50:
        level = "MEDIUM"

    else:
        level = "LOW"

    return {

        "agent":
            "Research Confidence",

        "confidence_score":
            score,

        "confidence_level":
            level

    }


if __name__ == "__main__":

    result = calculate_research_confidence(

        source_count = 4,

        agreement_count = 3,

        contradiction_count = 0

    )

    print(result)

    assert result["confidence_level"] == "HIGH"

    assert result["confidence_score"] == 100

