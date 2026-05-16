import json
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
STATE_FILE = DATA_DIR / "state_log.json"

def detect_mood(text):
    t = text.lower()
    if any(w in t for w in ["off","low","sad","down","struggling","overwhelmed"]):
        return "low"
    if any(w in t for w in ["good","great","happy","calm","grateful"]):
        return "high"
    return "neutral"

def extract_hps(text):
    import re
    m = re.search(r"(\\d+(\\.\\d+)?)\\s*hps", text.lower())
    return float(m.group(1)) if m else None

def build_state(user_input):
    return {"mood": detect_mood(user_input), "hps": extract_hps(user_input)}

def log_state(state):
    if not STATE_FILE.exists():
        STATE_FILE.write_text(json.dumps({"states": []}, indent=2))
    data = json.loads(STATE_FILE.read_text())
    data["states"].append({"state": state, "time": datetime.now().isoformat()})
    STATE_FILE.write_text(json.dumps(data, indent=2))
