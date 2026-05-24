from .storage import load_history

def retrieve_context(query: str, k=5):
    hist = load_history()
    q = query.lower().split()
    scored = []
    for h in hist:
        text = (h.get("user","") + " " + h.get("assistant","")).lower()
        score = sum(1 for w in q if w in text) + h.get("importance", 0)
        if score > 0:
            scored.append((score, h))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [h for _, h in scored[:k]]
