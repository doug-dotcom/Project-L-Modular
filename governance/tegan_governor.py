# =====================================================
# PROJECT L — TEGAN GOVERNOR
# AODS-4G-03
#
# Purpose:
# Governs cognition flow dynamically.
# Does NOT replace Tegan orchestration.
# Adds regulation + adaptive weighting.
# =====================================================


def _safe_float(value, default=0.0):

    try:
        return float(value)

    except Exception:
        return default


def _clamp(value, low=0.0, high=1.0):

    value = _safe_float(value, low)

    if value < low:
        return low

    if value > high:
        return high

    return value


# =====================================================
# BUILD GOVERNOR DECISION
# =====================================================

def build_governor_decision(

    runtime_state=None,

    physiology_state=None

):

    runtime_state = runtime_state or {}

    stress = _clamp(
        runtime_state.get("stress_level", 0.3)
    )

    emotional = _clamp(
        runtime_state.get("emotional_load", 0.3)
    )

    cognitive = _clamp(
        runtime_state.get("cognitive_load", 0.3)
    )

    depth = _clamp(
        runtime_state.get("conversation_depth", 0.3)
    )

    momentum = _clamp(
        runtime_state.get(
            "conversation_momentum",
            0.3
        )
    )

    truth = _clamp(
        runtime_state.get(
            "truth_mode_intensity",
            0.7
        )
    )

    # =================================================
    # PHYSIOLOGY STATE
    # =================================================

    physiology_state = (
        physiology_state or {}
    )

    body_battery = physiology_state.get(
        "body_battery"
    )

    physiological_stress = physiology_state.get(
        "stress_score"
    )

    sleep_score = physiology_state.get(
        "sleep_score"
    )

    decision = {

        "response_depth": "normal",

        "compression_mode": "balanced",

        "truth_mode": "standard",

        "support_mode": False,

        "browser_allowed": True,

        "memory_depth": 8,

        "priority": "balanced"
    }

    # =================================================
    # HIGH STRESS
    # =================================================

    if stress >= 0.75:

        decision["response_depth"] = "gentle"

        decision["compression_mode"] = "high"

        decision["support_mode"] = True

        decision["memory_depth"] = 5

        decision["priority"] = (
            "emotional_stabilization"
        )

    # =================================================
    # HIGH COGNITION
    # =================================================

    if cognitive >= 0.70:

        decision["response_depth"] = "deep"

        decision["compression_mode"] = "low"

        decision["memory_depth"] = 15

        decision["priority"] = "cognition"

    # =================================================
    # HIGH DEPTH
    # =================================================

    if depth >= 0.75:

        decision["response_depth"] = "deep"

    # =================================================
    # HIGH MOMENTUM
    # =================================================

    if momentum >= 0.80:

        decision["memory_depth"] += 5

    # =================================================
    # LOW BODY BATTERY
    # =================================================

    if body_battery is not None:

        if body_battery <= 20:

            decision["response_depth"] = "gentle"

            decision["compression_mode"] = "high"

            decision["support_mode"] = True

            decision["priority"] = (
                "recovery_stabilization"
            )

            decision["memory_depth"] = 5

            decision["low_body_battery_detected"] = True

    # =================================================
    # HIGH PHYSIOLOGICAL STRESS
    # =================================================

    if physiological_stress is not None:

        if physiological_stress >= 75:

            decision["support_mode"] = True

            decision["priority"] = (
                "physiological_regulation"
            )

            decision["high_stress_detected"] = True

    # =================================================
    # LOW SLEEP
    # =================================================

    if sleep_score is not None:

        if sleep_score <= 40:

            decision["response_depth"] = "gentle"

            decision["priority"] = (
                "recovery_support"
            )

            decision["low_sleep_detected"] = True

    # =================================================
    # STRICT TRUTH MODE
    # =================================================

    if truth >= 0.80:

        decision["truth_mode"] = "strict"

    return decision


# =====================================================
# SUMMARY
# =====================================================

def summarize_governor(decision):

    if not isinstance(decision, dict):

        return "invalid governor"

    return (

        f"depth={decision.get('response_depth')} | "

        f"compression={decision.get('compression_mode')} | "

        f"truth={decision.get('truth_mode')} | "

        f"memory_depth={decision.get('memory_depth')} | "

        f"priority={decision.get('priority')} | "

        f"battery_guard={decision.get('low_body_battery_detected', False)}"

    )

