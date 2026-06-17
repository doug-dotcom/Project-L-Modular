# =====================================================
# INSIGHT GENERATOR
# TIER 2 - AODS 4
# =====================================================

from typing import Dict, List


def generate_insights(
    patterns: Dict,
    gaps: List[str]
) -> Dict:

    insights = []

    for theme, count in patterns.items():

        insights.append({

            "type":
                "pattern",

            "insight":
                f"Theme '{theme}' appeared {count} times"

        })

    for gap in gaps:

        insights.append({

            "type":
                "gap",

            "insight":
                f"Further research required for '{gap}'"

        })

    return {

        "agent":
            "Insight Generator",

        "insight_count":
            len(insights),

        "insights":
            insights

    }


if __name__ == "__main__":

    patterns = {

        "memory": 5,

        "research": 3

    }

    gaps = [

        "wisdom",

        "intuition"

    ]

    result = generate_insights(

        patterns,

        gaps

    )

    print(result)

    assert result["insight_count"] == 4

    assert "memory" in result["insights"][0]["insight"]

