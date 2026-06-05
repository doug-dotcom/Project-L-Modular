import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

COLLISION_FILE = ROOT / "collisions.json"

def load_collisions():

    with open(
        COLLISION_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)

def show_collisions():

    collisions = load_collisions()

    print()
    print("=== DOMAIN COLLISIONS ===")
    print()

    for item in collisions:

        print(
            f"{item['winner']} > {item['loser']}"
        )

        print(
            f"Reason: {item['reason']}"
        )

        print(
            f"Confidence: {item['confidence']}"
        )

        print("-" * 50)

if __name__ == "__main__":

    show_collisions()
