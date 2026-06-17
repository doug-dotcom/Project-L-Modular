# =====================================================
# KNOWLEDGE RECALL
# TIER 5 - AODS 6
# =====================================================

from typing import Dict, List


def recall_knowledge(
    query: str,
    knowledge_items: List[Dict]
) -> Dict:

    query = str(
        query
    ).strip().lower()

    matches = []

    for item in knowledge_items or []:

        content = str(

            item.get(
                "content",
                ""
            )

        ).lower()

        if query in content:

            matches.append(
                item
            )

    return {

        "agent":
            "Knowledge Recall",

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
            "content":
                "Exercise improves cognition"
        },

        {
            "content":
                "Sleep improves memory"
        }

    ]

    result = recall_knowledge(

        "exercise",

        sample

    )

    print(result)

    assert result["match_count"] == 1

    assert "exercise" in \
        result["matches"][0]["content"].lower()

