# =========================================================
# FIONA — CALM FINANCE ROUTING V1
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
    "loss": 4

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
    "hug": -4

}

TRIGGER_THRESHOLD = 5

# =========================================================
# SHOULD HANDLE
# =========================================================

def should_handle(message: str):

    text = message.lower()

    score = 0

    positive_hits = []
    suppression_hits = []

    # =====================================================
    # POSITIVE SCORING
    # =====================================================

    for keyword, value in FINANCE_KEYWORDS.items():

        if keyword in text:

            score += value

            positive_hits.append(keyword)

    # =====================================================
    # SUPPRESSION SCORING
    # =====================================================

    for keyword, value in SUPPRESSION_KEYWORDS.items():

        if keyword in text:

            score += value

            suppression_hits.append(keyword)

    # =====================================================
    # DEBUG OUTPUT
    # =====================================================

    print("")
    print("💰 FIONA ROUTING DEBUG")
    print("MESSAGE:", message)
    print("FINANCE SCORE:", score)
    print("POSITIVE:", positive_hits)
    print("SUPPRESSION:", suppression_hits)

    if score >= TRIGGER_THRESHOLD:

        print("✅ FIONA ACTIVATED")
        return True

    print("🛑 FIONA SUPPRESSED")
    return False

# =========================================================
# HANDLE REQUEST
# =====================================================

def handle_finance_request(message: str):

    return f"""

# 💰 Fiona Finance

I detected a finance-related request.

Message:
{message}

This is currently the calm routing version of Fiona.

"""
