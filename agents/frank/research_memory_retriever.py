# =====================================================
# RESEARCH MEMORY RETRIEVER
# TIER 4 - AODS 2
# =====================================================

from typing import Dict, List


def retrieve_research_memory(
    query: str,
    research_records: List[Dict]
) -> Dict:

    query = query.lower().strip()

    matches = []

    for record in research_records or []:

        question = str(
            record.get(
                "question",
                ""
            )
        ).lower()

        summary = str(
            record.get(
                "summary",
                ""
            )
        ).lower()

        if (
            query in question
            or
            query in summary
        ):

            matches.append(
                record
            )

    return {

        "agent":
            "Research Memory Retriever",

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

            "question":
                "How does exercise affect cognition?",

            "summary":
                "Exercise improves cognition"

        },

        {

            "question":
                "How does sleep affect memory?",

            "summary":
                "Sleep improves memory"

        }

    ]

    result = retrieve_research_memory(

        "exercise",

        sample

    )

    print(result)

    assert result["match_count"] == 1

    assert "exercise" in result["matches"][0]["question"].lower()

