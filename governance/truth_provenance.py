# =====================================================
# PROJECT L — TRUTH PROVENANCE
# AODS-4G-05
#
# Purpose:
# Track source origin and confidence.
# Reinforces Truth Mode operationally.
# Does NOT replace cognition systems.
# =====================================================


VALID_SOURCE_TYPES = [

    "memory",

    "browser",

    "inference",

    "user_provided",

    "runtime",

    "unknown"
]


# =====================================================
# CLAMP CONFIDENCE
# =====================================================

def normalize_confidence(confidence):

    confidence = str(confidence).lower()

    if confidence not in [

        "high",
        "medium",
        "low"

    ]:

        return "medium"

    return confidence


# =====================================================
# BUILD PROVENANCE
# =====================================================

def build_truth_provenance(

    source_type="unknown",

    confidence="medium",

    browser_used=False,

    inferred=False,

    memory_used=False

):

    source_type = str(source_type).lower()

    if source_type not in VALID_SOURCE_TYPES:

        source_type = "unknown"

    confidence = normalize_confidence(
        confidence
    )

    provenance = {

        "source_type": source_type,

        "confidence": confidence,

        "browser_used": bool(browser_used),

        "inferred": bool(inferred),

        "memory_used": bool(memory_used),

        "truth_mode": True
    }

    return provenance


# =====================================================
# BUILD DISCLOSURE
# =====================================================

def build_truth_disclosure(provenance):

    if not isinstance(provenance, dict):

        return ""

    source_type = provenance.get(
        "source_type",
        "unknown"
    )

    confidence = provenance.get(
        "confidence",
        "medium"
    )

    if source_type == "browser":

        return (
            "This response used live browser research."
        )

    if source_type == "memory":

        return (
            "This response used stored memory context."
        )

    if source_type == "inference":

        return (
            "This response contains inferred reasoning."
        )

    if confidence == "low":

        return (
            "Confidence is low. Verification recommended."
        )

    return ""


# =====================================================
# SUMMARY
# =====================================================

def summarize_provenance(provenance):

    if not isinstance(provenance, dict):

        return "invalid provenance"

    return (

        f"source={provenance.get('source_type')} | "

        f"confidence={provenance.get('confidence')} | "

        f"browser={provenance.get('browser_used')} | "

        f"inferred={provenance.get('inferred')}"

    )
