import re

# =====================================================
# DOMAIN KEYWORDS
# =====================================================

DOMAIN_PATTERNS = {

    "short_term_identity": [
        "identity",
        "mask",
        "purpose",
        "meaning",
        "who i am",
        "self worth",
        "doug",
        "dougie",
        "douglas"
    ],

    "short_term_family": [
        "family",
        "kids",
        "father",
        "daughter",
        "son",
        "iyla",
        "ashton",
        "luella",
        "mehlia"
    ],

    "short_term_relationships": [
        "relationship",
        "partner",
        "girlfriend",
        "boyfriend",
        "friend",
        "tamara",
        "monica",
        "rhee"
    ],

    "short_term_health": [
        "health",
        "adhd",
        "sleep",
        "doctor",
        "medication",
        "hps",
        "therapy",
        "pauline"
    ],

    "short_term_finance": [
        "money",
        "finance",
        "bill",
        "debt",
        "insurance",
        "capstone",
        "zurich",
        "ato"
    ],

    "short_term_sport": [
        "sport",
        "hockey",
        "basketball",
        "netball",
        "surf",
        "punt",
        "racing"
    ],

    "short_term_knowledge": [
        "philosophy",
        "science",
        "history",
        "psychology",
        "ai",
        "consciousness",
        "bostrom",
        "harari"
    ],

    "short_term_recovery": [
        "recovery",
        "meeting",
        "healing",
        "step",
        "regulation",
        "addiction",
        "na"
    ],

    "short_term_project_l": [
        "project l",
        "memory",
        "runtime",
        "server.py",
        "cognition",
        "supabase",
        "aods",
        "ellie"
    ]
}

# =====================================================
# CLASSIFY
# =====================================================

def classify_message(text):

    text = re.sub(
        r"\s+",
        " ",
        str(text).lower()
    ).strip()

    scores = {}

    for domain, patterns in DOMAIN_PATTERNS.items():

        score = 0

        for p in patterns:

            if p in text:
                score += 1

        scores[domain] = score

    best_domain = max(scores, key=scores.get)

    if scores[best_domain] == 0:
        return "short_term_general"

    return best_domain

# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    tests = [

        "I feel scared about money",
        "Project L memory runtime flow",
        "My kids are important to me",
        "Recovery meeting tonight",
        "I feel lost with identity"
    ]

    for t in tests:

        result = classify_message(t)

        print("")
        print(f"INPUT: {t}")
        print(f"DOMAIN: {result}")

