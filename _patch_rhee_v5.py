from pathlib import Path

path = Path(r"C:\Shine_L\agents\rhee\rhee_v3.py")
text = path.read_text(encoding="utf-8")

start = text.index("def exhaustive_requested")
end = text.index("def build_context", start)

replacement = r'''
STOP_WORDS = {
    "please", "recall", "remember", "conversation", "conversations",
    "where", "when", "what", "who", "the", "and", "for", "with",
    "all", "every", "everything", "said", "tell", "about", "find",
    "rest", "there", "more", "list", "show", "give", "can", "you",
    "me", "my", "i"
}

def exhaustive_requested(query):
    text = safe_text(query).lower()
    return any(trigger in text for trigger in [
        "all", "every", "everything", "complete", "entire",
        "full", "whole", "list", "find the rest", "there are more"
    ])

def evidence_mode_requested(query):
    text = safe_text(query).lower()
    return any(trigger in text for trigger in [
        "all", "every", "exact", "quote", "list", "timeline",
        "chronology", "date", "time", "times", "when"
    ])

def expanded_query_terms(query):
    text = safe_text(query).lower()

    base_terms = [
        word for word in query_words(query)
        if word not in STOP_WORDS and len(word) >= 3
    ]

    terms = set(base_terms)

    phrase_map = {
        "good night": [
            "good night",
            "goodnight",
            "sleep well",
            "went to bed",
            "go to bed",
            "bedtime",
            "sleep protocol",
            "sleep duration",
            "record the time",
            "recorded the time",
        ],
        "sleep": [
            "sleep",
            "sleep well",
            "went to bed",
            "go to bed",
            "bedtime",
            "sleep protocol",
            "sleep duration",
            "good night",
            "goodnight",
            "wake",
            "woke",
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
            score += 120 if " " in term else 50

    if not matched:
        return 0

    if role == "user":
        score += 15

    if source == "chat":
        score += 5

    score += min(len(content) // 400, 10)

    return score

def build_raw_recall_packet(query, limit=40):
    rows = load_all_raw_catchall()
    scored = []
    exhaustive = exhaustive_requested(query)
    evidence_mode = evidence_mode_requested(query)

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

    selected = scored[:120] if exhaustive else scored[:limit]
    selected.reverse()

    print("=" * 60)
    print(f"RAW ROWS SEARCHED : {len(rows)}")
    print(f"RAW MATCHES FOUND : {len(scored)}")
    print(f"RAW MATCHES SENT  : {len(selected)}")
    print(f"EVIDENCE MODE     : {evidence_mode}")
    print("=" * 60)

    lines = []
    lines.append("RHEE V5 EVIDENCE MODE RAW RECALL")
    lines.append(f"QUERY: {query}")
    lines.append(f"RAW ROWS SEARCHED: {len(rows)}")
    lines.append(f"RAW MATCHES FOUND: {len(scored)}")
    lines.append(f"EXHAUSTIVE MODE: {exhaustive}")
    lines.append(f"EVIDENCE MODE: {evidence_mode}")
    lines.append(f"RAW MATCHES INJECTED: {len(selected)}")
    lines.append("")

    if evidence_mode:
        lines.append("RHEE EVIDENCE PROTOCOL")
        lines.append("The records below are retrieved evidence.")
        lines.append("Do not invent dates, times, events, or missing details.")
        lines.append("Do not merge separate records into one event.")
        lines.append("Do not reorder unless the record clearly contains a date or time.")
        lines.append("If the evidence is incomplete, say it is incomplete.")
        lines.append("When listing results, quote or closely preserve the retrieved wording.")
        lines.append("")

    seen = set()
    record_no = 1

    for row in selected:
        role = safe_text(row.get("role", "unknown")).upper()
        content = safe_text(row.get("content", ""))
        created_at = safe_text(row.get("created_at", ""))
        row_id = safe_text(row.get("id", ""))

        if not content:
            continue

        fingerprint = content[:220].lower()

        if fingerprint in seen:
            continue

        seen.add(fingerprint)

        lines.append(f"RECORD {record_no}")
        lines.append(f"ID: {row_id}")
        lines.append(f"CREATED_AT: {created_at}")
        lines.append(f"ROLE: {role}")
        lines.append(f"SCORE: {row.get('_score', 0)}")
        lines.append("CONTENT:")
        lines.append(content[:700] if evidence_mode else content[:900])
        lines.append("")
        record_no += 1

    return "\n".join(lines)

'''

text = text[:start] + replacement + "\n" + text[end:]
text = text.replace('"version": "v4.0"', '"version": "v5.0"')
text = text.replace('"version": "v3.1"', '"version": "v5.0"')
text = text.replace("RHEE V4 MEMORY CONTEXT", "RHEE V5 MEMORY CONTEXT")
text = text.replace("RHEE V3.1 MEMORY CONTEXT", "RHEE V5 MEMORY CONTEXT")

path.write_text(text, encoding="utf-8")
print("Rhee v5 evidence mode written.")
