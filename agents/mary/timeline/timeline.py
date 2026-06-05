import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

TIMELINE_FILE = ROOT / "timeline.json"

def load_timeline():

    if not TIMELINE_FILE.exists():
        return []

    with open(TIMELINE_FILE,"r",encoding="utf-8") as f:
        return json.load(f)

def save_timeline(data):

    with open(TIMELINE_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2)

def add_event(date,event):

    data = load_timeline()

    entry = {
        "date": date,
        "event": event
    }

    data.append(entry)

    data.sort(key=lambda x: x["date"])

    save_timeline(data)

    return data

if __name__ == "__main__":

    result = add_event(
        "2026-06-04",
        "Terri appointment"
    )

    print(result)
