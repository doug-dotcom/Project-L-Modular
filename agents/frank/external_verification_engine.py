# =====================================================
# EXTERNAL VERIFICATION ENGINE
# TIER 4 - AODS 4
# =====================================================

from typing import Dict


def verify_answer(
    internal_answer: str,
    external_answer: str
) -> Dict:

    internal = str(
        internal_answer
    ).strip().lower()

    external = str(
        external_answer
    ).strip().lower()

    verified = (

        internal == external

    )

    return {

        "agent":
            "External Verification Engine",

        "verified":
            verified,

        "internal_answer":
            internal_answer,

        "external_answer":
            external_answer

    }


if __name__ == "__main__":

    result = verify_answer(

        "Exercise improves cognition",

        "Exercise improves cognition"

    )

    print(result)

    assert result["verified"] is True

