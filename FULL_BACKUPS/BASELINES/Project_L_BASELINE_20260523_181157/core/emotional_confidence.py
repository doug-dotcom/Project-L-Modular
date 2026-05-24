EMOTIONAL_KEYWORDS = {

    "overwhelmed": 5,
    "panic": 5,
    "anxious": 4,
    "sad": 4,
    "lost": 4,
    "confused": 3,
    "calm": 2,
    "peace": 3,
    "stress": 4,
    "tired": 2,
    "hurt": 4,
    "lonely": 4,
    "grateful": 2

}


def calculate_emotional_confidence(message):

    text = message.lower()

    score = 0
    hits = []

    for keyword, value in EMOTIONAL_KEYWORDS.items():

        if keyword in text:

            score += value
            hits.append(keyword)

    confidence = "low"

    if score >= 8:
        confidence = "high"

    elif score >= 4:
        confidence = "medium"

    print("")
    print("🧠 EMOTIONAL CONFIDENCE")
    print("SCORE:", score)
    print("CONFIDENCE:", confidence)
    print("HITS:", hits)

    return {
        "score": score,
        "confidence": confidence,
        "hits": hits
    }


def build_calm_cognition_layer(confidence_data):

    confidence = confidence_data.get(
        "confidence",
        "low"
    )

    if confidence == "high":

        return """

CALM COGNITION MODE:
- Slow pacing
- Reduce information density
- Use short sections
- Focus on reassurance and clarity
- Avoid overwhelming detail
- Prefer one next step only

"""

    elif confidence == "medium":

        return """

BALANCED COGNITION MODE:
- Maintain calm structure
- Moderate detail
- Clear formatting
- Avoid cognitive overload

"""

    return """

NORMAL COGNITION MODE:
- Standard conversational pacing
- Clear and warm communication

"""