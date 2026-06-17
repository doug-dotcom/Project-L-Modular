# =====================================================
# INSIGHT RANKING
# TIER 2 - AODS 5
# =====================================================

from typing import List, Dict


def rank_insights(
    insights: List[Dict]
) -> List[Dict]:

    ranked = sorted(

        insights,

        key=lambda x: (

            x.get(
                "importance",
                0
            ),

            x.get(
                "confidence",
                0
            )

        ),

        reverse=True

    )

    return ranked


if __name__ == "__main__":

    sample = [

        {
            "insight":
                "Exercise reduces dementia risk",

            "importance":
                95,

            "confidence":
                90

        },

        {
            "insight":
                "Sleep improves cognition",

            "importance":
                80,

            "confidence":
                85

        },

        {
            "insight":
                "Cold showers may help memory",

            "importance":
                40,

            "confidence":
                50

        }

    ]

    result = rank_insights(
        sample
    )

    print(result)

    assert result[0]["importance"] == 95

    assert result[-1]["importance"] == 40

