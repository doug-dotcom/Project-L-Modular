# =====================================================
# KNOWLEDGE RANKING
# TIER 2 - AODS 2
# =====================================================

from typing import List, Dict


def rank_knowledge(
    knowledge_items: List[Dict]
) -> List[Dict]:

    ranked = sorted(

        knowledge_items,

        key=lambda x: (

            x.get(
                "confidence_score",
                0
            ),

            x.get(
                "evidence_count",
                0
            )

        ),

        reverse=True

    )

    return ranked


if __name__ == "__main__":

    sample = [

        {
            "topic": "memory",
            "confidence_score": 70,
            "evidence_count": 3
        },

        {
            "topic": "patterns",
            "confidence_score": 95,
            "evidence_count": 5
        },

        {
            "topic": "wisdom",
            "confidence_score": 80,
            "evidence_count": 2
        }

    ]

    result = rank_knowledge(
        sample
    )

    print(result)

    assert result[0]["topic"] == "patterns"

    assert result[1]["topic"] == "wisdom"

    assert result[2]["topic"] == "memory"

