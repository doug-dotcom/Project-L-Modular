import json
import os
from collections import defaultdict

BASE = os.path.dirname(__file__)
OUTCOME_PATH = os.path.join(BASE, "memory_outcomes.json")

def analyze_patterns():
    try:
        with open(OUTCOME_PATH, "r") as f:
            data = json.load(f)
    except:
        return {}

    stats = defaultdict(lambda: {"worked": 0, "failed": 0})

    for entry in data:
        pattern = entry.get("pattern")
        outcome = entry.get("outcome")

        if not pattern:
            continue

        if outcome == "worked":
            stats[pattern]["worked"] += 1
        elif outcome == "failed":
            stats[pattern]["failed"] += 1

    return stats


def get_best_action(pattern_key):
    stats = analyze_patterns()

    if pattern_key not in stats:
        return None

    data = stats[pattern_key]
    total = data["worked"] + data["failed"]

    if total == 0:
        return None

    success_rate = int((data["worked"] / total) * 100)

    return {
        "success_rate": success_rate,
        "worked": data["worked"],
        "failed": data["failed"]
    }
