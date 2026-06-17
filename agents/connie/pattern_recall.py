# =====================================================
# PATTERN RECALL
# TIER 5 - AODS 7
# =====================================================

from typing import Dict, List


def recall_patterns(
    query: str,
    patterns: List[Dict]
) -> Dict:

    query = str(
        query
    ).strip().lower()

    matches = []

    for pattern in patterns or []:

        name = str(

            pattern.get(
                "pattern",
                ""
            )

        ).lower()

        if query in name:

            matches.append(
                pattern
            )

    return {

        "agent":
            "Pattern Recall",

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
            "pattern":
                "memory"
        },

        {
            "pattern":
                "research"
        },

        {
            "pattern":
                "memory retrieval"
        }

    ]

    result = recall_patterns(

        "memory",

        sample

    )

    print(result)

    assert result["match_count"] == 2

    assert "memory" in \
        result["matches"][0]["pattern"].lower()

