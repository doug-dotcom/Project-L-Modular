# =====================================================
# FRANK -> SARA BRIDGE
# RAT PACK
# AODS 11
# =====================================================

def run_frank_sara_bridge(
    mary_packet
):
    """
    Sara Bridge

    Converts Mary meaning packets into
    ranked research outputs.

    No dependency on Sara memory processing.

    Sara's role here is research ranking.
    """

    values = (
        mary_packet.get(
            "values",
            []
        )
        or
        []
    )

    patterns = (
        mary_packet.get(
            "patterns",
            []
        )
        or
        []
    )

    relationships = (
        mary_packet.get(
            "relationships",
            []
        )
        or
        []
    )

    identity_relevance = int(
        mary_packet.get(
            "identity_relevance",
            0
        )
        or
        0
    )

    importance = 50

    importance += (
        len(values) * 10
    )

    importance += (
        len(patterns) * 15
    )

    importance += (
        len(relationships) * 5
    )

    importance += int(
        identity_relevance / 5
    )

    importance = min(
        importance,
        100
    )

    salience = importance

    anchor = (
        importance >= 80
    )

    return {

        "agent":
            "Frank Sara Bridge",

        "importance":
            importance,

        "salience":
            salience,

        "anchor":
            anchor,

        "ranking":

            "HIGH"

            if importance >= 80

            else

            "MEDIUM"

            if importance >= 60

            else

            "LOW"

    }


# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    sample = {

        "values": [

            "growth",
            "truth"

        ],

        "patterns": [

            "project l development"

        ],

        "relationships": [

            "Ashton"

        ],

        "identity_relevance":
            75

    }

    result = (
        run_frank_sara_bridge(
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
