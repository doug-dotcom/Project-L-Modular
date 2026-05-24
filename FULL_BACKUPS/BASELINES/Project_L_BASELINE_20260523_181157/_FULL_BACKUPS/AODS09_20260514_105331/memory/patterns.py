from .storage import load_history

def recent_states(n=5):
    hist = load_history()
    return [h.get("state", {}).get("mood") for h in hist[-n:]]

def detect_overwhelm_trend():
    rs = recent_states(5)
    return rs.count("low") >= 3
