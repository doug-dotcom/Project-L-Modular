import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

IMPORTANCE_FILE = ROOT / "importance.json"

def load_importance():

    try:

        with open(
            IMPORTANCE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except:

        return []

def rank_domains():

    data = load_importance()

    ranked = sorted(
        data,
        key=lambda x: x.get(
            "importance_score",
            0
        ),
        reverse=True
    )

    return ranked

if __name__ == "__main__":

    ranked = rank_domains()

    print()
    print("=== DOMAIN IMPORTANCE RANKING ===")
    print()

    for item in ranked:

        print(
            f"{item['domain']} "
            f"({item['importance_score']})"
        )

        print(
            f"Reason: "
            f"{item['reason']}"
        )

        print("-" * 50)
