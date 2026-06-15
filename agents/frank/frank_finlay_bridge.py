# =====================================================
# FRANK -> FINLAY BRIDGE
# RAT PACK
# AODS 9
# =====================================================

from agents.finlay.finlay import (
    run_finlay_finder
)


# =====================================================
# BUILD REFLECTION
# =====================================================

def _build_reflection(
    ronnie_result
):

    if not ronnie_result:
        return {}

    if "ronnie_result" in ronnie_result:

        return ronnie_result.get(
            "ronnie_result",
            {}
        )

    return ronnie_result


# =====================================================
# BRIDGE
# =====================================================

def run_frank_finlay_bridge(
    ronnie_output
):

    reflection = (
        _build_reflection(
            ronnie_output
        )
    )

    finlay_result = (
        run_finlay_finder(
            reflection
        )
    )

    return {

        "agent":
            "Frank Finlay Bridge",

        "reflection":
            reflection,

        "finlay_result":
            finlay_result

    }


# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    sample = {

        "ronnie_result": {

            "what_happened":
                "Exercise, sleep and social connection repeatedly appeared.",

            "what_stood_out": [

                "Exercise appeared repeatedly",

                "Sleep appeared repeatedly",

                "Social connection appeared repeatedly"

            ]

        }

    }

    result = (
        run_frank_finlay_bridge(
            sample
        )
    )

    import json

    print(
        json.dumps(
            result,
            indent=2
        )
    )
