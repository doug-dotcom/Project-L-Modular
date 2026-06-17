# =====================================================
# RESEARCH COMPRESSOR
# TIER 2 - AODS 8
# =====================================================

from typing import List, Dict


def compress_research(
    findings: List[str],
    max_items: int = 5
) -> Dict:

    findings = findings or []

    compressed = findings[:max_items]

    return {

        "agent":
            "Research Compressor",

        "original_count":
            len(findings),

        "compressed_count":
            len(compressed),

        "compressed_findings":
            compressed

    }


if __name__ == "__main__":

    sample = [

        "Exercise improves cognition",

        "Sleep improves cognition",

        "Social connection improves wellbeing",

        "Exercise improves cardiovascular health",

        "Mediterranean diet may reduce risk",

        "Lifelong learning may help cognition"

    ]

    result = compress_research(
        sample
    )

    print(result)

    assert result["original_count"] == 6

    assert result["compressed_count"] == 5

