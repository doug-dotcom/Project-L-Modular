# =====================================================
# CONNIE EXPORT
# TIER 3 - AODS 7
# =====================================================

import json
from pathlib import Path
from typing import Dict


def export_corpus(
    dataset: Dict,
    output_file: str
) -> Dict:

    path = Path(
        output_file
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(

        path,

        "w",

        encoding="utf-8"

    ) as f:

        json.dump(

            dataset,

            f,

            indent=2

        )

    return {

        "agent":
            "Connie Export",

        "status":
            "ok",

        "file":
            str(path)

    }


if __name__ == "__main__":

    dataset = {

        "research": {

            "record_count": 10

        },

        "themes": {

            "theme_count": 5

        }

    }

    result = export_corpus(

        dataset,

        "exports/test_corpus.json"

    )

    print(result)

    assert result["status"] == "ok"

