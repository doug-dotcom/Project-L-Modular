# =====================================================
# SMART ROUTING
# TIER 4 - AODS 5
# =====================================================

from typing import Dict


def route_query(
    query: str
) -> Dict:

    query = str(
        query
    ).lower()

    route = "general"

    if any(

        word in query

        for word in [

            "research",
            "study",
            "evidence",
            "science"

        ]

    ):

        route = "research"

    elif any(

        word in query

        for word in [

            "memory",
            "remember",
            "recall"

        ]

    ):

        route = "memory"

    elif any(

        word in query

        for word in [

            "pattern",
            "trend"

        ]

    ):

        route = "patterns"

    return {

        "agent":
            "Smart Routing",

        "query":
            query,

        "route":
            route

    }


if __name__ == "__main__":

    result = route_query(

        "Research dementia studies"

    )

    print(result)

    assert result["route"] == "research"

