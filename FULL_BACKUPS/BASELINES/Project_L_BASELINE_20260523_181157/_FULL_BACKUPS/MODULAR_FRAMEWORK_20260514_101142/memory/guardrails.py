import json, os, datetime

BASE = os.path.dirname(__file__)
FILE = os.path.join(BASE, "guardrails.json")

def load():
    if not os.path.exists(FILE):
        return []
    return json.load(open(FILE))

def save(data):
    json.dump(data, open(FILE,"w"), indent=2)

def check(user_msg: str):
    flags = []
    t = user_msg.lower()

    if "aods" in t and ("many" in t or "stack" in t):
        flags.append("Risk: multiple AODS stacking detected")

    if "broken" in t or "not working" in t:
        flags.append("Risk: instability reported")

    data = load()
    entry = {
        "time": str(datetime.datetime.now()),
        "msg": user_msg,
        "flags": flags
    }
    data.append(entry)
    save(data)

    return flags
