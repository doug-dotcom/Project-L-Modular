# =====================================================
# INTUITION RECALL
# TIER 5 - AODS 9
# =====================================================

from typing import Dict, List


def recall_intuition(
    query: str,
    intuitions: List[Dict]
) -> Dict:

    query = str(
        query
    ).strip().lower()

    matches = []

    for item in intuitions or []:

        prediction = str(

            item.get(
                "prediction",
                ""
            )

        ).lower()

        if query in prediction:

            matches.append(
                item
            )

    return {

        "agent":
            "Intuition Recall",

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
            "prediction":
                "Memory retrieval usage will increase"
        },

        {
            "prediction":
                "Research corpus will expand"
        },

        {
            "prediction":
                "Memory systems will become central"
        }

    ]

    result = recall_intuition(

        "memory",

        sample

    )

    print(result)

    assert result["match_count"] == 2

    assert "memory" in \
        result["matches"][0]["prediction"].lower()

