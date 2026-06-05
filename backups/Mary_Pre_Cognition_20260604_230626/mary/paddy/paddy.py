import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PATTERN_FILE = ROOT / "patterns.json"

def load_patterns():

    if not PATTERN_FILE.exists():
        return []

    with open(PATTERN_FILE,"r",encoding="utf-8") as f:
        return json.load(f)

def save_patterns(data):

    with open(PATTERN_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2)

def add_pattern(name, sequence):

    data = load_patterns()

    entry = {
        "pattern": name,
        "sequence": sequence
    }

    data.append(entry)

    save_patterns(data)

    return entry

if __name__ == "__main__":

    result = add_pattern(
        "Pipeline Fatigue",
        [
            "Progress",
            "Delay",
            "Follow-up",
            "Progress"
        ]
    )

    print(result)
