# =========================================================
# GRACIE — CALM LEGACY ROUTING V1
# =========================================================

LEGACY_KEYWORDS = {

    "legacy": 5,
    "save this memory": 6,
    "remember this moment": 6,
    "write my story": 6,
    "for my kids": 5,
    "for my children": 5,
    "future generations": 5,
    "book idea": 4,
    "preserve this": 5,
    "life lesson": 4,
    "journal entry": 5,
    "reflection": 3,
    "spoken memory": 5,
    "save this story": 6

}

SUPPRESSION_KEYWORDS = {

    "recall": -7,
    "retrieve": -6,
    "tell me": -5,
    "what do you know": -5,
    "work history": -8,
    "career history": -8,
    "employment": -6,
    "summarise": -5,
    "summary": -5,
    "explain": -5,
    "memory audit": -8,
    "who am i": -8,
    "what happened": -5,
    "show me": -5

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

    for keyword, value in LEGACY_KEYWORDS.items():

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
    print("📖 GRACIE ROUTING DEBUG")
    print("MESSAGE:", message)
    print("LEGACY SCORE:", score)
    print("POSITIVE:", positive_hits)
    print("SUPPRESSION:", suppression_hits)

    if score >= TRIGGER_THRESHOLD:

        print("✅ GRACIE ACTIVATED")
        return True

    print("🛑 GRACIE SUPPRESSED")
    return False

# =========================================================
# HANDLE LEGACY REQUEST
# =========================================================

def handle_legacy_request(message: str):

    return f"""

# 📖 Gracie Legacy Builder

I detected a true legacy preservation request.

Message:
{message}

This is currently the calm routing version of Gracie.

"""
