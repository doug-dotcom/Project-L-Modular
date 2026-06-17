# =====================================================
# COMPRESSION OPTIMISER
# TIER 2 - AODS 11
# =====================================================

from typing import Dict


def optimise_compression(
    original_count: int,
    compressed_count: int
) -> Dict:

    if original_count <= 0:

        ratio = 0

    else:

        ratio = round(

            compressed_count / original_count,

            2

        )

    reduction = round(

        (1 - ratio) * 100,

        2

    )

    return {

        "agent":
            "Compression Optimiser",

        "original_count":
            original_count,

        "compressed_count":
            compressed_count,

        "compression_ratio":
            ratio,

        "reduction_percent":
            reduction

    }


if __name__ == "__main__":

    result = optimise_compression(

        original_count = 100,

        compressed_count = 25

    )

    print(result)

    assert result["compression_ratio"] == 0.25

    assert result["reduction_percent"] == 75.0

