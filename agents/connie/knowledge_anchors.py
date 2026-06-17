# =====================================================
# KNOWLEDGE ANCHORS
# TIER 1 - AODS 8
# =====================================================

from typing import List, Dict


def build_anchors(
    findings: List[str]
) -> Dict:

    anchors = []

    for finding in findings or []:

        anchors.append({

            "anchor": finding,

            "strength": len(
                str(finding).split()
            )

        })

    anchors = sorted(

        anchors,

        key=lambda x: x["strength"],

        reverse=True

    )

    return {

        "agent":
            "Knowledge Anchors",

        "anchor_count":
            len(anchors),

        "anchors":
            anchors

    }


if __name__ == "__main__":

    sample = [

        "exercise reduces dementia risk",

        "sleep improves cognition",

        "social connection improves wellbeing"

    ]

    result = build_anchors(
        sample
    )

    print(result)

    assert result["anchor_count"] == 3

    assert result["anchors"][0]["strength"] >= 3

