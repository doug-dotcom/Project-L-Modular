import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOMAIN_FILE = (
    ROOT
    / "memory"
    / "domains"
    / "sport.json"
)

def load_domain():

    with open(
        DOMAIN_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)

def save_domain(data):

    with open(
        DOMAIN_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )

def enrich_sport_domain():

    data = load_domain()

    # -------------------------------------------------
    # DOMAIN LEVEL ENRICHMENT
    # -------------------------------------------------

    if isinstance(data, dict):

        data["mary_processed"] = True

        data["mary_version"] = "1.0"

        data["importance_score"] = 90

        data["meaning"] = (
            "Sport has been a lifelong source "
            "of belonging, competition, identity "
            "and personal growth."
        )

        data["narrative"] = (
            "Hockey remained one of the most "
            "consistent threads throughout "
            "Doug's military, civilian and "
            "recovery journey."
        )

        save_domain(data)

        return data

    return {
        "error":
            "sport.json is not a domain-level object"
    }

if __name__ == "__main__":

    result = enrich_sport_domain()

    print()

    print("=== MARY DOMAIN UNDERSTANDING ===")

    print()

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )
