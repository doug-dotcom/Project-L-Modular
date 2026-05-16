import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
HISTORY_FILE = DATA_DIR / "history.json"

def load_history():
    if not HISTORY_FILE.exists():
        return []
    data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return data.get("history", [])

def save_history(history):
    HISTORY_FILE.write_text(json.dumps({"history": history}, indent=2), encoding="utf-8")
