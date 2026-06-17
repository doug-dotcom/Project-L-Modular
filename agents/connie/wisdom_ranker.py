# =====================================================
# WISDOM RANKER
# TIER 2 - AODS 3
# =====================================================

from typing import List, Dict


def rank_wisdom(
    wisdom_items: List[Dict]
) -> List[Dict]:

    ranked = sorted(

        wisdom_items,

        key=lambda x: (

            x.get(
                "confidence_score",
                0
            ),

            x.get(
                "consensus_score",
                0
            ),

            x.get(
                "evidence_count",
                0
            )

        ),

        reverse=True

    )

    return ranked


if __name__ == "__main__":

    sample = [

        {
            "insight": "Exercise reduces dementia risk",
            "confidence_score": 95,
            "consensus_score": 90,
            "evidence_count": 12
        },

        {
            "insight": "Sleep may help cognition",
            "confidence_score": 80,
            "consensus_score": 70,
            "evidence_count": 8
        },

        {
            "insight": "Cold showers improve memory",
            "confidence_score": 60,
            "consensus_score": 40,
            "evidence_count": 2
        }

    ]

    result = rank_wisdom(
        sample
    )

    print(result)

    assert result[0]["insight"] == "Exercise reduces dementia risk"

    assert result[2]["insight"] == "Cold showers improve memory"

