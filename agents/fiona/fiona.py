from agents.fiona.fiona_ingest import analyse_latest_csv

# =========================================================
# FIONA — CALM FINANCE ROUTING V2 TOKEN SAFE
# =========================================================

FINANCE_KEYWORDS = {
    "budget": 4,
    "bank": 4,
    "mortgage": 5,
    "loan": 5,
    "debt": 5,
    "credit": 4,
    "finance": 5,
    "financial": 5,
    "investment": 4,
    "income": 4,
    "expenses": 4,
    "expense": 4,
    "tax": 4,
    "super": 3,
    "shares": 3,
    "portfolio": 4,
    "saving": 3,
    "savings": 3,
    "spending money": 5,
    "cost": 3,
    "pricing": 3,
    "profit": 4,
    "loss": 4,
    "csv": 6,
    "transactions": 6
}

SUPPRESSION_KEYWORDS = {
    "kids": -4,
    "children": -4,
    "daughter": -4,
    "son": -4,
    "family": -3,
    "love": -3,
    "memory": -3,
    "reflection": -3,
    "proud": -3,
    "time with": -6,
    "spending time": -8,
    "trampoline": -4,
    "fishing": -3,
    "feel": -2,
    "emotion": -2,
    "hug": -4,
    "lyndal": -10,
    "parents": -8,
    "singer": -8,
    "person": -6
}

TRIGGER_THRESHOLD = 6

MAX_FIONA_OUTPUT_CHARS = 8000
MAX_MESSAGE_CHARS = 1200

# =========================================================
# SAFE TEXT LIMITER
# =========================================================

def clamp_text(text, limit=MAX_FIONA_OUTPUT_CHARS):
    if not text:
        return ""

    text = str(text)

    if len(text) <= limit:
        return text

    return (
        text[:limit]
        + "\n\n...[FIONA OUTPUT TRIMMED — TOKEN SAFETY LIMIT APPLIED]..."
    )

# =========================================================
# SHOULD HANDLE
# =========================================================

def should_handle(message: str):
    text = (message or "").lower()[:MAX_MESSAGE_CHARS]

    score = 0
    positive_hits = []
    suppression_hits = []

    for keyword, value in FINANCE_KEYWORDS.items():
        if keyword in text:
            score += value
            positive_hits.append(keyword)

    for keyword, value in SUPPRESSION_KEYWORDS.items():
        if keyword in text:
            score += value
            suppression_hits.append(keyword)

    print("")
    print("FIONA ROUTING DEBUG")
    print("MESSAGE:", text)
    print("FINANCE SCORE:", score)
    print("POSITIVE:", positive_hits)
    print("SUPPRESSION:", suppression_hits)

    if score >= TRIGGER_THRESHOLD:
        print("FIONA ACTIVATED")
        return True

    print("FIONA SUPPRESSED")
    return False

# =========================================================
# HANDLE REQUEST
# =========================================================

def handle_finance_request(message: str):
    text = (message or "").lower()[:MAX_MESSAGE_CHARS]

    finance_action_terms = [
        "csv",
        "uploaded",
        "transactions",
        "spending",
        "review my transactions",
        "analyse my transactions",
        "analyze my transactions",
        "bank statement",
        "finance report"
    ]

    if any(term in text for term in finance_action_terms):
        result = analyse_latest_csv()
        return clamp_text(result)

    return clamp_text(f"""
# Financial Analysis

I detected a finance-related request, but I did not load any CSV data.

Message:
{message}

Try asking:
"Fiona, review my uploaded transactions CSV."
""")