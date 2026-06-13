# =====================================================
# AODS 8 - COACH
# LEARNING LOOPERS ORCHESTRATOR
# =====================================================

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.ronnie.ronnie import run_ronnie_reflector
from agents.finlay.finlay import run_finlay_finder
from agents.chase.chase import run_chase_checker
from agents.mannie.mannie import run_mannie_mapper
from agents.gary.gary import run_gary_guardian
from agents.ian.ian import run_ian_integration
from agents.allegra.allegra import create_llgr


def run_coach(experience):

    ronnie = run_ronnie_reflector(
        experience
    )

    finlay = run_finlay_finder(
        ronnie
    )

    chase = run_chase_checker(
        finlay
    )

    mannie = run_mannie_mapper(
        chase
    )

    gary = run_gary_guardian(
        mannie
    )

    ian = run_ian_integration(
        gary
    )

    llgr = create_llgr(

        reflection=
            ronnie.get(
                "what_stood_out",
                []
            ),

        lesson=
            finlay.get(
                "lesson",
                ""
            ),

        validated=
            chase.get(
                "validated",
                False
            ),

        adjustment=
            mannie.get(
                "adjustment",
                ""
            ),

        agency_score=
            gary.get(
                "agency_score",
                0
            ),

        keys_owner=
            gary.get(
                "keys_owner",
                "Unknown"
            ),

        validation_count=
            ian.get(
                "validation_count",
                1
            ),

        contradiction_count=
            ian.get(
                "contradiction_count",
                0
            ),

        confidence_score=
            ian.get(
                "confidence_score",
                50
            ),

        evidence=
            ian.get(
                "supporting_evidence",
                []
            ),

        contradiction_evidence=
            ian.get(
                "contradicting_evidence",
                []
            )

    )

    
    # =====================================================
    # ALLEGRA STORAGE
    # =====================================================

    try:

        from agents.allegra.llgr_storage import (
            store_llgr
        )

        store_llgr(
            llgr
        )

    except Exception as e:

        print(
            f"ALLEGRA ERROR: {e}"
        )

    return {


        "coach":
            "Coach",

        "team":
            "Learning Loopers",

        "ronnie":
            ronnie,

        "finlay":
            finlay,

        "chase":
            chase,

        "mannie":
            mannie,

        "gary":
            gary,

        "ian":
            ian,

        "llgr":
            llgr

    }


if __name__ == "__main__":

    sample = """

    Doug noticed he kept looking
    to Pauline for validation.

    The pattern connected to mentors,
    Dad, Sean Graham and Walshy.

    The keys metaphor stood out.

    """

    result = run_coach(
        sample
    )

    import json

    print(
        json.dumps(
            result,
            indent=2
        )
    )


