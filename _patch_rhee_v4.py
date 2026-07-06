from pathlib import Path

path = Path(r"C:\Shine_L\agents\rhee\rhee_v3.py")
text = path.read_text(encoding="utf-8")

start = text.index("def exhaustive_requested")
end = text.index("def build_context", start)

replacement = r'''
def exhaustive_requested(query):
    text = safe_text(query).lower()

    triggers = [
        "all",
        "every",
        "everything",
        "complete",
        "entire",
        "full",
        "whole",
        "list",
        "find the rest",
        "there are more",
    ]

    return any(trigger in text for trigger in triggers)

def expanded_query_terms(query):
    text = safe_text(query).lower()
    terms = set(query_words(query))

    phrase_map = {
        "good night": [
            "good night",
            "goodnight",
            "sleep well",
            "sleep protocol",
            "went to bed",
            "go to bed",
            "bedtime",
            "sleep duration",
            "record the time",
            "recorded the time",
        ],
        "sleep": [
            "sleep",
            "sleep well",
            "sleep protocol",
            "went to bed",
            "go to bed",
            "bedtime",
            "sleep duration",
            "good night",
            "goodnight",
            "woke",
            "wake",
        ],
        "pauline": [
            "pauline",
            "psychologist",
            "therapy",
            "session",
            "jung",
            "individuation",
            "defusion",
            "useful",
            "loved",
            "keys to doug",
        ],
        "luella": [
            "luella",
            "daughter",
            "alien",
            "braces",
            "kitten",
            "kayd",
        ],
        "project l": [
            "project l",
            "rhee",
            "memory",
            "raw catchall",
            "aods",
            "x",
            "mary",
            "rachel",
            "carol",
            "brittany",
        ],
    }

    for phrase, related in phrase_map.items():
        if phrase in text:
            for item in related:
                terms.add(item)

    return [t for t in terms if safe_text(t)]

def calculate_raw_score(row, query=""):
    score = 0
    matched = False

    terms = expanded_query_terms(query)
    content = safe_text(row.get("content", ""))
    content_lower = content.lower()
    role = safe_text(row.get("role", "")).lower()
    source = safe_text(row.get("source", "")).lower()

    for term in terms:
        term = safe_text(term).lower()

        if not term:
            continue

        if term in content_lower:
            matched = True

            if " " in term:
                score += 100
            else:
                score += 40

    # Strict safety gate:
    # no real match = no score.
    if not matched:
        return 0

    if role == "user":
        score += 15

    if source == "chat":
        score += 5

    # Length is only a tie-breaker AFTER a real match.
    score += min(len(content) // 250, 20)

    return score

def build_raw_recall_packet(query, limit=40):
    rows = load_all_raw_catchall()
    scored = []
    exhaustive = exhaustive_requested(query)

    for row in rows:
        score = calculate_raw_score(row, query)

        if score <= 0:
            continue

        row["_score"] = score
        scored.append(row)

    scored.sort(
        key=lambda x: x.get("_score", 0),
        reverse=True
    )

    if exhaustive:
        selected = scored[:120]
    else:
        selected = scored[:limit]

    selected.reverse()

    print("=" * 60)
    print(f"RAW ROWS SEARCHED : {len(rows)}")
    print(f"RAW MATCHES FOUND : {len(scored)}")
    print(f"RAW MATCHES SENT  : {len(selected)}")
    print("=" * 60)

    lines = []
    lines.append("RHEE V4 STRICT RAW SEARCH")
    lines.append(f"QUERY: {query}")
    lines.append(f"RAW ROWS SEARCHED: {len(rows)}")
    lines.append(f"RAW MATCHES FOUND: {len(scored)}")
    lines.append(f"EXHAUSTIVE MODE: {exhaustive}")
    lines.append(f"RAW MATCHES INJECTED: {len(selected)}")
    lines.append("")

    seen = set()

    for row in selected:
        role = safe_text(row.get("role", "unknown")).upper()
        content = safe_text(row.get("content", ""))

        if not content:
            continue

        fingerprint = content[:180].lower()

        if fingerprint in seen:
            continue

        seen.add(fingerprint)

        if exhaustive:
            lines.append(f"{role}: {content[:500]}")
        else:
            lines.append(f"{role}: {content[:900]}")

    return "\n".join(lines)

'''

text = text[:start] + replacement + "\n" + text[end:]
text = text.replace('"version": "v3.1"', '"version": "v4.0"')
text = text.replace("RHEE V3.1 MEMORY CONTEXT", "RHEE V4 MEMORY CONTEXT")

path.write_text(text, encoding="utf-8")
print("Rhee v4 strict raw search written.")
