# =====================================================
# RESEARCH CORPUS BUILDER
# TIER 3 - AODS 1
# =====================================================

from typing import List, Dict, Any


def build_research_corpus(
    research_records: List[Dict[str, Any]]
) -> Dict[str, Any]:

    corpus = []

    for record in research_records or []:

        corpus.append({

            "question":
                record.get("question"),

            "summary":
                record.get("summary"),

            "findings":
                record.get("findings", []),

            "lessons":
                record.get("lessons", [])

        })

    return {

        "agent":
            "Research Corpus Builder",

        "record_count":
            len(corpus),

        "corpus":
            corpus

    }


if __name__ == "__main__":

    sample = [

        {

            "question":
                "How does exercise affect cognition?",

            "summary":
                "Exercise improves cognition",

            "findings":
                ["Improved memory"],

            "lessons":
                ["Exercise supports brain health"]

        }

    ]

    result = build_research_corpus(
        sample
    )

    print(result)

    assert result["record_count"] == 1

    assert result["corpus"][0]["summary"] == "Exercise improves cognition"

