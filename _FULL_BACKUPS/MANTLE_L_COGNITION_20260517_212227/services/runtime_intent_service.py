# =====================================================
# runtime_intent_service.py
# AODS 79
# =====================================================

import json
from pathlib import Path
from datetime import datetime

INTENT_FILE = (
    Path("intent")
    / "runtime_intent_map.json"
)

def load_intent_map():

    try:
        with open(
            INTENT_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:

        return {
            "intent_patterns": {}
        }

def intent_patterns():

    data = load_intent_map()

    return data.get(
        "intent_patterns",
        {}
    )

def detect_intents(text):

    text = str(text or "").lower()

    patterns = intent_patterns()

    matches = []

    for intent, keywords in patterns.items():

        score = 0
        found = []

        for keyword in keywords:

            if keyword in text:

                score += 1
                found.append(keyword)

        if score > 0:

            matches.append({
                "intent": intent,
                "score": score,
                "matched_keywords": found
            })

    matches = sorted(
        matches,
        key=lambda x: x["score"],
        reverse=True
    )

    return matches

def dominant_intent(text):

    matches = detect_intents(text)

    if not matches:

        return {
            "intent": "general",
            "score": 0
        }

    return matches[0]

def intent_summary(text):

    dominant = dominant_intent(text)

    matches = detect_intents(text)

    return {
        "timestamp": datetime.now().isoformat(),

        "input": text,

        "dominant_intent": dominant,

        "all_matches": matches,

        "status": "mapped"
    }

def intent_status():

    patterns = intent_patterns()

    return {
        "timestamp": datetime.now().isoformat(),

        "intent_types": len(patterns),

        "mapped_intents": list(
            patterns.keys()
        ),

        "status": "online"
    }
