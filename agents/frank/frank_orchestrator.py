# =====================================================
# FRANK ORCHESTRATOR
# RAT PACK
# AODS 12
# =====================================================

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agents.quinn.quinn import run_quinn
from agents.scout.scout import run_scout
from agents.vera.vera import run_vera
from agents.dot.dot import run_dot

from agents.rannie.rannie import run_rannie

from agents.frank.frank import run_frank

from agents.frank.frank_chase_bridge import (
    run_frank_chase_bridge
)

from agents.frank.frank_ronnie_bridge import (
    run_frank_ronnie_bridge
)

from agents.frank.frank_finlay_bridge import (
    run_frank_finlay_bridge
)

from agents.frank.frank_mary_bridge import (
    run_frank_mary_bridge
)

from agents.frank.frank_sara_bridge import (
    run_frank_sara_bridge
)



# =====================================================
# ORCHESTRATOR
# =====================================================


def is_deep_research(question):

    question = str(
        question or ""
    ).lower()

    triggers = [

        "deep research",
        "research thoroughly",
        "full research",
        "investigate",
        "comprehensive research"

    ]

    return any(
        t in question
        for t in triggers
    )


def run_rat_pack(
    question
):

    quinn = run_quinn(
        question
    )

    search_queries = (
        quinn.get(
            "search_queries",
            []
        )
    )

    deep_mode = is_deep_research(
        question
    )

    if not deep_mode:

        search_queries = (
            search_queries[:3]
        )

        print(
            f"FAST MODE QUERY LIMIT: {len(search_queries)}"
        )

    stage = time.perf_counter()

    print(
        f"SCOUT QUERY COUNT: {len(search_queries)}"
    )

    scout = run_scout(
        search_queries
    )

    print(
        f"SCOUT: "
        f"{time.perf_counter() - stage:.2f}s"
    )

    sources = (
        scout.get(
            "sources",
            []
        )
    )

    vera = run_vera(
        sources
    )

    dot = run_dot(
        sources
    )

    rannie = run_rannie(
        dot
    )

    frank = run_frank(
        question,
        {
            "results":
                sources
        }
    )

    deep_mode = is_deep_research(
        question
    )

    print(
        f"DEEP MODE: {deep_mode}"
    )

    if not deep_mode:

        print(
            "FAST RESEARCH MODE"
        )

        return {

            "quinn":
                quinn,

            "scout":
                scout,

            "frank":
                frank

        }

    chase = (
        run_frank_chase_bridge(
            frank
        )
    )

    ronnie = (
        run_frank_ronnie_bridge(
            frank,
            rannie
        )
    )

    finlay = (
        run_frank_finlay_bridge(
            ronnie
        )
    )

    mary = (
        run_frank_mary_bridge(
            frank,
            finlay.get(
                "finlay_result",
                {}
            ),
            rannie
        )
    )

    sara = (
        run_frank_sara_bridge(
            mary.get(
                "mary_packet",
                {}
            )
        )
    )

    return {

        "agent":
            "Frank Orchestrator",

        "question":
            question,

        "quinn":
            quinn,

        "scout":
            scout,

        "vera":
            vera,

        "dot":
            dot,

        "rannie":
            rannie,

        "frank":
            frank,

        "chase":
            chase,

        "ronnie":
            ronnie,

        "finlay":
            finlay,

        "mary":
            mary,

        "sara":
            sara

    }


# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    result = run_rat_pack(
        "Research dementia prevention"
    )

    print(
        result.keys()
    )








