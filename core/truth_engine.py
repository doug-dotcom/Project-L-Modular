# =====================================================
# PROJECT L — TRUTH ENGINE
# =====================================================

TRUTH_MODES = {
    "retrieved_memory": "Known from memory retrieval",
    "live_research": "Verified through live tool research",
    "inference": "Reasoned inference from context",
    "speculation": "Unverified possibility",
    "unknown": "Insufficient evidence"
}

# =====================================================
# CLASSIFY SOURCE
# =====================================================

def classify_source(
    retrieved_memories=None,
    browser_used=False,
    explicit_uncertainty=False
):

    retrieved_memories = retrieved_memories or []

    if browser_used:
        return "live_research"

    if retrieved_memories:
        return "retrieved_memory"

    if explicit_uncertainty:
        return "unknown"

    return "inference"

# =====================================================
# BUILD TRUTH PROMPT
# =====================================================

def build_truth_prompt(source_type):

    labels = {

        "retrieved_memory":
            "This response is based on retrieved memory.",

        "live_research":
            "This response is based on live verified research.",

        "inference":
            "This response contains inferred reasoning and may not be verified.",

        "speculation":
            "This response includes speculation and uncertain assumptions.",

        "unknown":
            "There is insufficient evidence to answer confidently."
    }

    return labels.get(
        source_type,
        "Truth state unknown."
    )
