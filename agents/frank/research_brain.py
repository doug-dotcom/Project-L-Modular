# =====================================================
# RESEARCH BRAIN
# TIER 4 - AODS 6
# =====================================================

from typing import Dict

from agents.frank.smart_routing import (
    route_query
)


def run_research_brain(
    query: str
) -> Dict:

    route = route_query(
        query
    )

    return {

        "agent":
            "Research Brain",

        "query":
            query,

        "route":
            route["route"],

        "status":
            "processed"

    }


if __name__ == "__main__":

    result = run_research_brain(

        "Research dementia studies"

    )

    print(result)

    assert result["route"] == "research"

    assert result["status"] == "processed"

