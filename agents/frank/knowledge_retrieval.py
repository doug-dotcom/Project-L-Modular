# =====================================================
# KNOWLEDGE RETRIEVAL
# TIER 1 - AODS 9
# =====================================================

from typing import List, Dict, Any


def retrieve_knowledge(
    query: str,
    records: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:

    query = str(
        query
    ).strip().lower()

    matches = []

    for record in records or []:

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

    return matches


if __name__ == "__main__":

    records = [

        {
            "id": 1,
            "content": "Exercise reduces dementia risk"
        },

        {
            "id": 2,
            "content": "Sleep improves cognition"
        },

        {
            "id": 3,
            "content": "Exercise improves cardiovascular health"
        }

    ]

    result = retrieve_knowledge(

        "exercise",

        records

    )

    print(result)

    assert len(result) == 2

    assert result[0]["id"] == 1

