# =====================================================
# CONTRADICTION HUNTER
# TIER 1 - AODS 14
# =====================================================

from typing import List, Dict, Any


def hunt_contradictions(
    records: List[Dict[str, Any]]
) -> Dict[str, Any]:

    contradictions = []

    for record in records or []:

        question = record.get(
            "question",
            ""
        )

        items = (
            record.get(
                "contradictions",
                []
            )
            or
            []
        )

        for item in items:

            contradictions.append({

                "question":
                    question,

                "contradiction":
                    item

            })

    return {

        "agent":
            "Contradiction Hunter",

        "record_count":
            len(records or []),

        "contradiction_count":
            len(contradictions),

        "contradictions":
            contradictions

    }


if __name__ == "__main__":

    sample = [

        {
            "question":
                "Does exercise help cognition?",

            "contradictions": [

                "Some studies show benefit; one study shows no effect."

            ]

        },

        {
            "question":
                "Does sleep improve memory?",

            "contradictions": []

        }

    ]

    result = hunt_contradictions(
        sample
    )

    print(result)

    assert result["record_count"] == 2

    assert result["contradiction_count"] == 1

    assert "exercise" in result["contradictions"][0]["question"].lower()

