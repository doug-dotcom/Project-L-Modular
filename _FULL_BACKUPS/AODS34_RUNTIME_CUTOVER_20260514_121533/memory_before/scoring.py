def score_message(text: str, tags: list):
    if "identity_core" in tags: return 1.0
    if "identity" in tags: return 0.9
    if "mood_low" in tags or "mood_high" in tags: return 0.8
    if "question" in tags: return 0.6
    return 0.3
