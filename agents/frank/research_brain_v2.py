# =====================================================
# RESEARCH BRAIN V2
# TIER 5 - AODS 10
# =====================================================

from typing import Dict

from agents.frank.smart_routing import (
    route_query
)

from agents.frank.memory_first_search import (
    memory_first_search
)


def run_research_brain_v2(
    query: str,
    memory_records: list
) -> Dict:

    route = route_query(
        query
    )

    memory = memory_first_search(
        query,
        memory_records
    )

    return {

        "agent":
            "Research Brain v2",

        "query":
            query,

        "route":
            route["route"],

        "memory_hit":
            memory["memory_hit"],

        "match_count":
            memory["match_count"],

        "status":
            "processed"

    }


if __name__ == "__main__":

    sample = [

        {
            "content":
                "Exercise improves cognition"
        }

    ]

    result = run_research_brain_v2(

        "exercise",

        sample

    )

    print(result)

    assert result["memory_hit"] is True

    assert result["match_count"] == 1

    assert result["status"] == "processed"

