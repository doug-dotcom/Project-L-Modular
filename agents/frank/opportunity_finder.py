# =====================================================
# OPPORTUNITY FINDER
# TIER 1 - AODS 12
# =====================================================

from typing import List, Dict


def find_opportunities(
    gaps: List[str],
    contradictions: List[str]
) -> Dict:

    opportunities = []

    for gap in gaps or []:

        opportunities.append({

            "type":
                "research_gap",

            "opportunity":
                f"Research {gap}"

        })

    for contradiction in contradictions or []:

        opportunities.append({

            "type":
                "contradiction",

            "opportunity":
                f"Investigate contradiction: {contradiction}"

        })

    return {

        "agent":
            "Opportunity Finder",

        "opportunity_count":
            len(opportunities),

        "opportunities":
            opportunities

    }


if __name__ == "__main__":

    result = find_opportunities(

        gaps = [

            "wisdom",
            "intuition"

        ],

        contradictions = [

            "exercise effectiveness"

        ]

    )

    print(result)

    assert result["opportunity_count"] == 3

