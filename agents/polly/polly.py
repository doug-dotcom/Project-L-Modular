# =====================================================
# POLLY
# RESEARCH PRESENTER
# =====================================================

from typing import Dict


def present_research(
    packet: Dict
) -> Dict:

    summary = packet.get(
        "summary",
        ""
    )

    confidence = packet.get(
        "confidence",
        "UNKNOWN"
    )

    findings = packet.get(
        "key_findings",
        []
    )

    unique_findings = []

    for finding in findings:

        if finding not in unique_findings:

            unique_findings.append(
                finding
            )

    briefing = []

    briefing.append(
        "Doug,"
    )

    briefing.append(
        ""
    )

    briefing.append(
        "Here's what Brittany found."
    )

    briefing.append(
        ""
    )

    briefing.append(
        f"Summary: {summary}"
    )

    briefing.append(
        ""
    )

    briefing.append(
        "Key Findings:"
    )

    for item in unique_findings:

        briefing.append(
            f"- {item}"
        )

    briefing.append(
        ""
    )

    briefing.append(
        f"Confidence: {confidence}"
    )

    return {

        "agent":
            "Polly",

        "finding_count":
            len(unique_findings),

        "briefing":
            "\n".join(
                briefing
            )

    }


if __name__ == "__main__":

    sample = {

        "summary":
            "31 Buranda Road estimated value $1.67M",

        "confidence":
            "HIGH",

        "key_findings": [

            "Last sold $680k in 2016",

            "6 bedrooms",

            "6 bedrooms",

            "1.48 acres"

        ]

    }

    result = present_research(
        sample
    )

    print(
        result["briefing"]
    )

    assert result["finding_count"] == 3

