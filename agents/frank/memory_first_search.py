# =====================================================
# MEMORY FIRST SEARCH
# TIER 4 - AODS 1
# =====================================================

from typing import Dict, List


def memory_first_search(
    query: str,
    memory_records: List[Dict]
) -> Dict:

    query = query.lower().strip()

    matches = []

    for record in memory_records or []:

        content = str(
            record.get(
                "content",
                ""
            )
        ).lower()

        if query in content:

            matches.append(
                record
            )

    return {

        "agent":
            "Memory First Search",

        "query":
            query,

        "match_count":
            len(matches),

        "matches":
            matches,

        "memory_hit":
            len(matches) > 0

    }


if __name__ == "__main__":

    sample = [

        {
            "content":
                "Exercise reduces dementia risk"
        },

        {
            "content":
                "Sleep improves cognition"
        }

    ]

    result = memory_first_search(

        "exercise",

        sample

    )

    print(result)

    assert result["memory_hit"] is True

    assert result["match_count"] == 1

