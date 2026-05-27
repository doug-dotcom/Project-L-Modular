import json
import os
from datetime import datetime

BASE = os.path.dirname(__file__)
PATTERN_PATH = os.path.join(BASE, "memory_patterns.json")
OUTCOME_PATH = os.path.join(BASE, "memory_outcomes.json")

def get_pattern(text):
    try:
        with open(PATTERN_PATH, "r") as f:
            data = json.load(f)
    except:
        return None, None

    t = text.lower()

    for key, value in data.items():
        for trigger in value.get("triggers", []):
            if trigger in t:
                return key, value

    return None, None


def log_outcome(pattern_key, user_input, result, outcome):
    try:
        with open(OUTCOME_PATH, "r") as f:
            data = json.load(f)
    except:
        data = []

    entry = {
        "time": str(datetime.now()),
        "pattern": pattern_key,
        "input": user_input,
        "action": result.get("A2"),
        "outcome": outcome
    }

    data.append(entry)

    with open(OUTCOME_PATH, "w") as f:
        json.dump(data, f, indent=2)

