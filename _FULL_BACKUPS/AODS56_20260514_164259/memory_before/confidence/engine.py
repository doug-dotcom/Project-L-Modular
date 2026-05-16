# ============================================================
# MEMORY CONFIDENCE ENGINE
# Operation Mnemosyne
# ============================================================

def calculate_basic_confidence(matches):

    if not matches:
        return {
            "confidence": "low",
            "score": 0,
            "reason": "no_matches"
        }

    try:
        top_score = matches[0].get("_score", 0)
    except Exception:
        top_score = 0

    if top_score >= 8:
        confidence = "high"
    elif top_score >= 4:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "confidence": confidence,
        "score": top_score,
        "reason": "score_threshold"
    }


def build_memory_confidence_layer(confidence_data):

    confidence = confidence_data.get(
        "confidence",
        "low"
    )

    if confidence == "low":

        return """

MEMORY CONFIDENCE: LOW

Instructions:
- Do not confidently invent missing details
- Prefer clarification over assumptions
- Say uncertainty clearly if memory is weak
- Avoid emotional fabrication

"""

    if confidence == "medium":

        return """

MEMORY CONFIDENCE: MEDIUM

Instructions:
- Use moderate confidence
- Distinguish memory from inference
- Mention uncertainty where appropriate

"""

    return """

MEMORY CONFIDENCE: HIGH

Instructions:
- Memory retrieval appears strong
- Use retrieved context confidently
- Still avoid exaggeration

"""


def confidence_status():

    return {
        "status": "online",
        "source": "memory/confidence",
        "operation": "AODS50"
    }
