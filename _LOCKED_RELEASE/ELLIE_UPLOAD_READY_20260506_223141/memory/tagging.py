def tag_message(text: str):
    t = text.lower()
    tags = []
    if any(w in t for w in ["sad","off","down","low","tired"]):
        tags.append("mood_low")
    if any(w in t for w in ["happy","good","great","calm","grateful"]):
        tags.append("mood_high")
    if "my name is" in t:
        tags.append("identity")
    if "born" in t or "birthday" in t:
        tags.append("identity_core")
    if "?" in t or t.startswith(("what","when","why","how")):
        tags.append("question")
    if any(w in t for w in ["punt","urge","itch","chasing"]):
        tags.append("dopamine_urge")
    return tags
