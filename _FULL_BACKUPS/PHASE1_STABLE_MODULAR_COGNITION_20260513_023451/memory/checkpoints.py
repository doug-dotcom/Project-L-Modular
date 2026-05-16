import json, os, datetime

BASE = os.path.dirname(__file__)
FILE = os.path.join(BASE, "checkpoints.json")

def load():
    if not os.path.exists(FILE):
        return []
    return json.load(open(FILE))

def save(data):
    json.dump(data, open(FILE,"w"), indent=2)

def create(label: str):
    data = load()
    entry = {
        "time": str(datetime.datetime.now()),
        "label": label
    }
    data.append(entry)
    save(data)
    return entry
