# =====================================================
# CONNIE DASHBOARD
# TIER 4 - AODS 10
# =====================================================

from typing import Dict


def build_connie_dashboard(
    corpus_count: int,
    wisdom_count: int,
    relationship_count: int,
    dataset_count: int
) -> Dict:

    return {

        "agent":
            "Connie Dashboard",

        "corpus_count":
            corpus_count,

        "wisdom_count":
            wisdom_count,

        "relationship_count":
            relationship_count,

        "dataset_count":
            dataset_count,

        "status":
            "healthy"

    }


if __name__ == "__main__":

    result = build_connie_dashboard(

        corpus_count = 500,

        wisdom_count = 120,

        relationship_count = 300,

        dataset_count = 50

    )

    print(result)

    assert result["status"] == "healthy"

    assert result["corpus_count"] == 500

    assert result["wisdom_count"] == 120

