# =====================================================
# PROJECT L — RECURSIVE SELF-ASSESSMENT
# AODS-4G-07
#
# Purpose:
# Lightweight cognition-quality check before response.
# This is NOT consciousness.
# It is grounding, uncertainty, and drift regulation.
# =====================================================


def _safe_bool(value):

    return bool(value)


def _safe_text(value):

    if value is None:
        return ""

    return str(value).strip()


# =====================================================
# SELF ASSESSMENT
# =====================================================

def assess_response_context(

    user_message="",

    runtime_state=None,

    governor_decision=None,

    provenance=None,

    memory_context="",

    draft_reply="",
        physiology_state=None,
):

    runtime_state = runtime_state or {}
    governor_decision = governor_decision or {}
    provenance = provenance or {}

    user_text = _safe_text(user_message).lower()
    memory_text = _safe_text(memory_context)
    draft_text = _safe_text(draft_reply)

    checks = {

        "grounded": True,

        "likely_inference": False,

        "needs_uncertainty": False,

        "possible_drift": False,

        "emotionally_sensitive": False,

        "browser_recommended": False,

        "response_mode": "normal",

        "assessment_notes": []
    }

    # =================================================
    # EMOTIONAL SENSITIVITY
    # =================================================

    emotional_terms = [

        "suicide",
        "self harm",
        "unsafe",
        "panic",
        "nightmare",
        "ptsd",
        "scared",
        "mental health",
        "medication",
        "dose",
        "blood pressure"

    ]

    for term in emotional_terms:

        if term in user_text:

            checks["emotionally_sensitive"] = True

            checks["response_mode"] = "gentle_grounded"

            checks["assessment_notes"].append(

                f"emotional_or_health_sensitive_term={term}"

            )

            break

    # =================================================
    # LIVE / CURRENT INFO NEEDS BROWSER
    # =================================================

    live_terms = [

        "latest",
        "current",
        "today",
        "now",
        "price",
        "law",
        "medical guideline",
        "dose limit",
        "research",
        "browser",
        "look up",
        "verify"

    ]

    for term in live_terms:

        if term in user_text:

            if not provenance.get("browser_used", False):

                checks["browser_recommended"] = True

                checks["needs_uncertainty"] = True

                checks["assessment_notes"].append(

                    f"live_verification_term={term}"

                )

            break

    # =================================================
    # MEMORY GROUNDING
    # =================================================

    if len(memory_text) < 20:

        if any(term in user_text for term in [

            "remember",
            "recall",
            "project l",
            "connie",
            "tegan",
            "brittany",
            "what did we"

        ]):

            checks["grounded"] = False

            checks["needs_uncertainty"] = True

            checks["assessment_notes"].append(

                "memory_requested_but_context_is_thin"

            )

    # =================================================
    # DRIFT DETECTION
    # =================================================

    drift_terms = [

        "not what i asked",
        "wrong root",
        "drift",
        "wrong format",
        "not the full script",
        "manual"

    ]

    for term in drift_terms:

        if term in user_text:

            checks["possible_drift"] = True

            checks["response_mode"] = "correction"

            checks["assessment_notes"].append(

                f"user_flagged_drift={term}"

            )

            break

    # =================================================
    # OVERCONFIDENCE CHECK
    # =================================================

    confidence = str(

        provenance.get(

            "confidence",

            "medium"

        )

    ).lower()

    if confidence == "low":

        checks["needs_uncertainty"] = True

        checks["assessment_notes"].append(

            "low_confidence_provenance"

        )

    # =================================================
    # GOVERNOR INTERACTION
    # =================================================

    if governor_decision.get("support_mode"):

        checks["emotionally_sensitive"] = True

        checks["response_mode"] = "supportive"

        checks["assessment_notes"].append(

            "governor_support_mode_active"

        )

    if governor_decision.get("truth_mode") == "strict":

        checks["needs_uncertainty"] = True

        checks["assessment_notes"].append(

            "strict_truth_mode_active"

        )

    # =================================================
    # DRAFT REPLY DRIFT CHECK
    # =================================================

    if draft_text:

        if "as an ai language model" in draft_text.lower():

            checks["possible_drift"] = True

            checks["assessment_notes"].append(

                "draft_contains_generic_ai_phrase"

            )

    return checks


# =====================================================
# BUILD SELF-ASSESSMENT PROMPT NOTE
# =====================================================

def build_self_assessment_note(checks):

    if not isinstance(checks, dict):

        return ""

    notes = checks.get("assessment_notes", [])

    if not notes:

        notes = ["no major concerns"]

    return (

        "SELF-ASSESSMENT:\n"

        f"grounded={checks.get('grounded')}\n"

        f"needs_uncertainty={checks.get('needs_uncertainty')}\n"

        f"possible_drift={checks.get('possible_drift')}\n"

        f"emotionally_sensitive={checks.get('emotionally_sensitive')}\n"

        f"browser_recommended={checks.get('browser_recommended')}\n"

        f"response_mode={checks.get('response_mode')}\n"

        f"notes={notes}"

    )


# =====================================================
# SUMMARY
# =====================================================

def summarize_self_assessment(checks):

    if not isinstance(checks, dict):

        return "invalid self-assessment"

    return (

        f"grounded={checks.get('grounded')} | "

        f"uncertainty={checks.get('needs_uncertainty')} | "

        f"drift={checks.get('possible_drift')} | "

        f"mode={checks.get('response_mode')}"

    )
