import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MEANING_FILE = ROOT / "meanings.json"

def load_meanings():

    if not MEANING_FILE.exists():
        return []

    with open(MEANING_FILE,"r",encoding="utf-8") as f:
        return json.load(f)

def save_meanings(data):

    with open(MEANING_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2)

def add_meaning(topic, meaning):

    data = load_meanings()

    entry = {
        "topic": topic,
        "meaning": meaning
    }

    data.append(entry)

    save_meanings(data)

    return entry

if __name__ == "__main__":

    result = add_meaning(
        "Pipeline Fatigue",
        "Doug is experiencing uncertainty, not failure."
    )

    print(result)
