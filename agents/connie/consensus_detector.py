# =====================================================
# CONSENSUS DETECTOR
# TIER 1 - AODS 7
# =====================================================

from collections import Counter
from typing import List, Dict


def detect_consensus(
    findings: List[str]
) -> Dict:

    counter = Counter()

    for finding in findings or []:

        clean = str(
            finding
        ).strip().lower()

        if clean:

            counter[clean] += 1

    total = len(
        findings or []
    )

    consensus = []

    for item, count in counter.items():

        percentage = round(
            (count / total) * 100,
            2
        )

        if percentage >= 50:

            consensus.append({

                "finding": item,

                "count": count,

                "agreement_percent": percentage

            })

    return {

        "agent":
            "Consensus Detector",

        "total_findings":
            total,

        "consensus":
            consensus

    }


if __name__ == "__main__":

    sample = [

        "exercise helps dementia prevention",
        "exercise helps dementia prevention",
        "exercise helps dementia prevention",
        "sleep improves cognition",
        "exercise helps dementia prevention"

    ]

    result = detect_consensus(
        sample
    )

    print(result)

    assert len(
        result["consensus"]
    ) == 1

    assert result["consensus"][0]["count"] == 4

