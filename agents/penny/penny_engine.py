import json

def build_hypotheses(
    observation,
    memories=None,
    associations=None
):

    observation = str(
        observation
    )

    hypotheses = []

    text = observation.lower()

    # =====================================
    # RELATIONSHIP CHANGE
    # =====================================

    if "different" in text:

        hypotheses.append({

            "hypothesis":
                "Something changed in the relationship",

            "confidence":
                70

        })

    # =====================================
    # OUT OF CHARACTER
    # =====================================

    if "out of character" in text:

        hypotheses.append({

            "hypothesis":
                "Internal state changed",

            "confidence":
                75

        })

    # =====================================
    # DEFAULT
    # =====================================

    if len(hypotheses) == 0:

        hypotheses.append({

            "hypothesis":
                "Insufficient information",

            "confidence":
                25

        })

    hypotheses.sort(

        key=lambda x:
            x["confidence"],

        reverse=True

    )

    return hypotheses


def penny_drop(

    observation,
    memories=None,
    associations=None

):

    memories = memories or []

    associations = associations or []

    hypotheses = build_hypotheses(

        observation,
        memories,
        associations

    )

    return {

        "observation":
            observation,

        "top_hypothesis":
            hypotheses[0],

        "all_hypotheses":
            hypotheses

    }


if __name__ == "__main__":

    observation = input(
        "Observation: "
    )

    result = penny_drop(
        observation
    )

    print()
    print("=" * 40)
    print("CAPTAIN PENNY")
    print("=" * 40)

    print()

    print(
        "Observation:"
    )

    print(
        result["observation"]
    )

    print()

    print(
        "Top Hypothesis:"
    )

    print(
        result["top_hypothesis"]
    )

    print()

    print(
        "All Hypotheses:"
    )

    print(
        json.dumps(
            result["all_hypotheses"],
            indent=2
        )
    )
