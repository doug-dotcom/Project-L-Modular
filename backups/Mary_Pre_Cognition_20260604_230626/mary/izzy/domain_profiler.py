import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

DOMAIN_DIR = ROOT / "memory" / "domains"

print()
print("ROOT =", ROOT)
print("DOMAIN_DIR =", DOMAIN_DIR)
print()

VALUE_HINTS = {

    "sport": [
        "Growth",
        "Connection",
        "Mastery",
        "Commitment"
    ],

    "recovery": [
        "Truth",
        "Growth",
        "Service",
        "Connection"
    ],

    "family": [
        "Love",
        "Presence",
        "Protection",
        "Self Respect"
    ],

    "project_l": [
        "Service",
        "Teaching",
        "Understanding",
        "Growth"
    ],

    "work": [
        "Achievement",
        "Contribution",
        "Integrity",
        "Growth"
    ],

    "health": [
        "Longevity",
        "Energy",
        "Freedom",
        "Wellbeing"
    ]
}

def profile_domain(domain_name):

    domain_file = (
        DOMAIN_DIR
        / f"{domain_name}.json"
    )

    if not domain_file.exists():

        return {

            "error":
                f"{domain_name} not found"

        }

    with open(
        domain_file,
        "r",
        encoding="utf-8"
    ) as f:

        memories = json.load(f)

    memory_count = (
        len(memories)
        if isinstance(memories, list)
        else 0
    )

    return {

        "domain":
            domain_name,

        "memory_count":
            memory_count,

        "candidate_values":
            VALUE_HINTS.get(
                domain_name,
                []
            )

    }

if __name__ == "__main__":

    for domain in [

        "family",
        "recovery",
        "sport",
        "project_l",
        "work"

    ]:

        result = profile_domain(domain)

        print()
        print("=" * 50)

        print(
            f"DOMAIN: {result['domain']}"
        )

        print(
            f"MEMORIES: {result['memory_count']}"
        )

        print()

        print(
            "Candidate Values:"
        )

        for value in result[
            "candidate_values"
        ]:

            print(
                f" - {value}"
            )
