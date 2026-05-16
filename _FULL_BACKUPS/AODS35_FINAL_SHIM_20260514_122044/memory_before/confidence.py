import random


MEMORY_CONFIDENCE_RULES = {

    "high": 8,
    "medium": 4

}


RELATIONSHIP_TERMS = [

    "daughter",
    "son",
    "wife",
    "husband",
    "partner",
    "girlfriend",
    "boyfriend",
    "mother",
    "father",
    "dog",
    "cat",
    "pet",
    "friend"

]


UNCERTAINTY_PHRASES = [

    "I may not fully understand the relationship context yet.",

    "I want to avoid making assumptions about the relationship.",

    "I understand this is important to you, though the context is still developing.",

    "I may be interpreting some emotional context rather than confirmed memory."

]


def calculate_memory_confidence(matches):

    if not matches:

        return {
            "confidence": "low",
            "score": 0
        }

    top_score = matches[0].get(
        "_score",
        0
    )

    confidence = "low"

    if top_score >= MEMORY_CONFIDENCE_RULES["high"]:

        confidence = "high"

    elif top_score >= MEMORY_CONFIDENCE_RULES["medium"]:

        confidence = "medium"

    print("")
    print("🧠 MEMORY CONFIDENCE")
    print("TOP SCORE:", top_score)
    print("CONFIDENCE:", confidence)

    return {
        "confidence": confidence,
        "score": top_score
    }


def detect_relationship_inference(reply):

    text = reply.lower()

    score = 0

    for term in RELATIONSHIP_TERMS:

        if term in text:

            score += 1

    return score >= 1


def detect_memory_uncertainty(user_msg):

    text = user_msg.lower()

    uncertainty_signals = [

        "forgot to tell you",
        "just remembered",
        "i think",
        "maybe",
        "might",
        "not sure"

    ]

    score = 0

    for signal in uncertainty_signals:

        if signal in text:

            score += 1

    return score >= 1


def apply_memory_confidence(
    reply,
    user_msg
):

    relationship_inference = detect_relationship_inference(
        reply
    )

    uncertainty_detected = detect_memory_uncertainty(
        user_msg
    )

    if relationship_inference and uncertainty_detected:

        phrase = random.choice(
            UNCERTAINTY_PHRASES
        )

        reply += "\n\n" + phrase

    return reply


def build_memory_confidence_layer(
    confidence_data
):

    confidence = confidence_data.get(
        "confidence",
        "low"
    )

    if confidence == "low":

        return \"\"\"

MEMORY CONFIDENCE: LOW

Instructions:
- Do not confidently invent missing details
- Prefer clarification over assumptions
- Say uncertainty clearly if memory is weak
- Avoid emotional fabrication

\"\"\"

    elif confidence == "medium":

        return \"\"\"

MEMORY CONFIDENCE: MEDIUM

Instructions:
- Use moderate confidence
- Distinguish memory from inference
- Mention uncertainty where appropriate

\"\"\"

    return \"\"\"

MEMORY CONFIDENCE: HIGH

Instructions:
- Memory retrieval appears strong
- Use retrieved context confidently
- Still avoid exaggeration

\"\"\"
