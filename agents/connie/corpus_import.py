# =====================================================
# CORPUS IMPORT
# TIER 5 - AODS 2
# =====================================================

import json
from pathlib import Path
from typing import Dict


def import_corpus(
    corpus_file: str
) -> Dict:

    path = Path(
        corpus_file
    )

    if not path.exists():

        return {

            "agent":
                "Corpus Import",

            "status":
                "file_not_found"

        }

    with open(

        path,

        "r",

        encoding="utf-8"

    ) as f:

        data = json.load(
            f
        )

    return {

        "agent":
            "Corpus Import",

        "status":
            "ok",

        "record_count":
            len(data)

            if isinstance(
                data,
                list
            )

            else 1,

        "corpus":
            data

    }


if __name__ == "__main__":

    test_file = "test_corpus.json"

    with open(

        test_file,

        "w",

        encoding="utf-8"

    ) as f:

        json.dump(

            [

                {
                    "question":
                        "How does exercise affect cognition?"
                },

                {
                    "question":
                        "How does sleep affect memory?"
                }

            ],

            f

        )

    result = import_corpus(
        test_file
    )

    print(result)

    assert result["status"] == "ok"

    assert result["record_count"] == 2

