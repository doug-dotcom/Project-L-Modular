import random
from .storage import load_history

def proactive_check():
    hist = load_history()
    if len(hist) < 3:
        return None
    recent = hist[-3:]
    for h in recent:
        t = (h.get("user","") or "").lower()
        if any(w in t for w in ["off","tired","low","overwhelmed"]):
            if random.random() < 0.4:
                return "Hey… you mentioned feeling a bit off earlier. How are you going now?"
    return None
