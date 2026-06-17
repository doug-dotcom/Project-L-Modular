# =====================================================
# WISDOM RECALL
# TIER 5 - AODS 8
# =====================================================

from typing import Dict, List


def recall_wisdom(
    query: str,
    wisdom_items: List[Dict]
) -> Dict:

    query = str(
        query
    ).strip().lower()

    matches = []

    for item in wisdom_items or []:

        wisdom = str(

            item.get(
                "wisdom",
                ""
            )

        ).lower()

        if query in wisdom:

            matches.append(
                item
            )

    return {

        "agent":
            "Wisdom Recall",

        "query":
            query,

        "match_count":
            len(matches),

        "matches":
            matches

    }


if __name__ == "__main__":

    sample = [

        {
            "wisdom":
                "Patterns create knowledge"
        },

        {
            "wisdom":
                "Knowledge creates wisdom"
        },

        {
            "wisdom":
                "Trust evidence over assumptions"
        }

    ]

    result = recall_wisdom(

        "knowledge",

        sample

    )

    print(result)

    assert result["match_count"] == 2

