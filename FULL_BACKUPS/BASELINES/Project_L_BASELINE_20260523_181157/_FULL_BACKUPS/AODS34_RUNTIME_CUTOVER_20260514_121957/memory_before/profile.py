import json, re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PROFILE_FILE = DATA_DIR / "profile.json"

def load_profile():
    if not PROFILE_FILE.exists():
        return {"name": None, "dob": None, "children": []}
    return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))

def save_profile(p):
    PROFILE_FILE.write_text(json.dumps(p, indent=2), encoding="utf-8")

def extract_name(text):
    m = re.search(r"my name is ([A-Za-z ]+)", text.lower())
    return m.group(1).title() if m else None

def extract_dob(text):
    m = re.search(r"(\\d{1,2})(?:st|nd|rd|th)? of ([A-Za-z]+) (\\d{4})", text.lower())
    if m:
        return f"{m.group(1)} {m.group(2).title()} {m.group(3)}"
    return None

def extract_children(text):
    out = []
    for name, dob in re.findall(r"([A-Za-z]+)[^\\d]*(\\d{1,2}/\\d{1,2}/\\d{4})", text):
        out.append({"name": name.title(), "dob": dob})
    return out

def update_profile(user_input):
    p = load_profile()
    name = extract_name(user_input)
    dob = extract_dob(user_input)
    kids = extract_children(user_input)
    if name: p["name"] = name
    if dob: p["dob"] = dob
    for k in kids:
        if k not in p["children"]:
            p["children"].append(k)
    save_profile(p)
    return p
