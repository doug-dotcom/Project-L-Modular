# =====================================================
# RECOVERY ↔ COGNITION MIRROR
# GARMIN AODS-07
#
# Purpose:
# Mirror physiological state into cognition guidance.
#
# Key Insight:
# Recovery state and cognition quality influence
# each other bidirectionally.
#
# This is NOT medical diagnosis.
# It is cognition-awareness support.
# =====================================================


# =====================================================
# SAFE INT
# =====================================================

def _safe_int(value):

    try:
        return int(value)

    except Exception:
        return None


# =====================================================
# BUILD MIRROR INSIGHT
# =====================================================

def build_recovery_cognition_mirror(

    physiology_state=None,

    runtime_state=None

):

    physiology_state = (
        physiology_state or {}
    )

    runtime_state = (
        runtime_state or {}
    )

    body_battery = _safe_int(
        physiology_state.get(
            "body_battery"
        )
    )

    stress = _safe_int(
        physiology_state.get(
            "stress_score"
        )
    )

    sleep = _safe_int(
        physiology_state.get(
            "sleep_score"
        )
    )

    cognitive_load = float(
        runtime_state.get(
            "cognitive_load",
            0.3
        )
    )

    emotional_load = float(
        runtime_state.get(
            "emotional_load",
            0.3
        )
    )

    insight = {

        "recovery_state": "stable",

        "cognition_state": "stable",

        "recommended_mode": "normal",

        "mirror_notes": []
    }

    # =================================================
    # LOW BATTERY
    # =================================================

    if body_battery is not None:

        if body_battery <= 20:

            insight["recovery_state"] = (
                "depleted"
            )

            insight["recommended_mode"] = (
                "gentle"
            )

            insight["mirror_notes"].append(

                "low_body_battery_may_reduce_cognitive_stability"

            )

    # =================================================
    # HIGH STRESS
    # =================================================

    if stress is not None:

        if stress >= 75:

            insight["recovery_state"] = (
                "high_stress"
            )

            insight["recommended_mode"] = (
                "stabilization"
            )

            insight["mirror_notes"].append(

                "high_physiological_stress_detected"

            )

    # =================================================
    # LOW SLEEP
    # =================================================

    if sleep is not None:

        if sleep <= 40:

            insight["mirror_notes"].append(

                "poor_sleep_may_increase_drift"

            )

    # =================================================
    # HIGH COGNITIVE LOAD
    # =================================================

    if cognitive_load >= 0.75:

        insight["cognition_state"] = (
            "deep_processing"
        )

        insight["mirror_notes"].append(

            "high_cognitive_depth_detected"

        )

    # =================================================
    # HIGH EMOTIONAL LOAD
    # =================================================

    if emotional_load >= 0.75:

        insight["cognition_state"] = (
            "emotionally_loaded"
        )

        insight["recommended_mode"] = (
            "grounded_support"
        )

        insight["mirror_notes"].append(

            "high_emotional_load_detected"

        )

    return insight


# =====================================================
# SUMMARY
# =====================================================

def summarize_recovery_mirror(insight):

    if not isinstance(insight, dict):

        return "invalid mirror"

    return (

        f"recovery={insight.get('recovery_state')} | "

        f"cognition={insight.get('cognition_state')} | "

        f"mode={insight.get('recommended_mode')}"

    )
