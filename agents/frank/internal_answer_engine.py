# =====================================================
# INTERNAL ANSWER ENGINE
# TIER 4 - AODS 3
# =====================================================

from typing import Dict, List


def generate_internal_answer(
    query: str,
    memory_matches: List[Dict]
) -> Dict:

    if not memory_matches:

        return {

            "agent":
                "Internal Answer Engine",

            "status":
                "no_answer",

            "answer":
                None

        }

    best_match = memory_matches[0]

    answer = best_match.get(

        "summary",

        best_match.get(
            "content",
            ""
        )

    )

    return {

        "agent":
            "Internal Answer Engine",

        "status":
            "answer_found",

        "answer":
            answer

    }


if __name__ == "__main__":

    sample = [

        {

            "question":
                "How does exercise affect cognition?",

            "summary":
                "Exercise improves cognition"

        }

    ]

    result = generate_internal_answer(

        "exercise",

        sample

    )

    print(result)

    assert result["status"] == "answer_found"

    assert result["answer"] == "Exercise improves cognition"

