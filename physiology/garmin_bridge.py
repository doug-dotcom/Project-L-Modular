# =====================================================
# GARMIN BRIDGE
# GARMIN AODS-01
#
# Purpose:
# Foundation for physiology-aware cognition.
# Connects physiological state into L cognition flow.
#
# This does NOT connect to Garmin APIs yet.
# This creates the cognition bridge layer FIRST.
# =====================================================


from datetime import datetime


# =====================================================
# DEFAULT PHYSIOLOGY STATE
# =====================================================

DEFAULT_PHYSIOLOGY_STATE = {

    "body_battery": None,

    "stress_score": None,

    "heart_rate": None,

    "sleep_score": None,

    "training_readiness": None,

    "hrv_status": None,

    "steps": None,

    "timestamp": None
}


# =====================================================
# SAFE INT
# =====================================================

def _safe_int(value):

    try:
        return int(value)

    except Exception:
        return None


# =====================================================
# BUILD PHYSIOLOGY STATE
# =====================================================

def build_physiology_state(

    body_battery=None,

    stress_score=None,

    heart_rate=None,

    sleep_score=None,

    training_readiness=None,

    hrv_status=None,

    steps=None

):

    state = dict(DEFAULT_PHYSIOLOGY_STATE)

    state["body_battery"] = (
        _safe_int(body_battery)
    )

    state["stress_score"] = (
        _safe_int(stress_score)
    )

    state["heart_rate"] = (
        _safe_int(heart_rate)
    )

    state["sleep_score"] = (
        _safe_int(sleep_score)
    )

    state["training_readiness"] = (
        _safe_int(training_readiness)
    )

    state["steps"] = (
        _safe_int(steps)
    )

    state["hrv_status"] = str(
        hrv_status
    )

    state["timestamp"] = str(
        datetime.now()
    )

    return state


# =====================================================
# PHYSIOLOGY COGNITION INTERPRETATION
# =====================================================

def interpret_physiology(state):

    if not isinstance(state, dict):

        return {

            "cognitive_mode": "normal",

            "support_mode": False,

            "notes": ["invalid physiology state"]

        }

    result = {

        "cognitive_mode": "normal",

        "support_mode": False,

        "notes": []
    }

    body_battery = state.get(
        "body_battery"
    )

    stress = state.get(
        "stress_score"
    )

    sleep = state.get(
        "sleep_score"
    )

    # =================================================
    # LOW BATTERY
    # =================================================

    if body_battery is not None:

        if body_battery <= 20:

            result["cognitive_mode"] = (
                "low_energy"
            )

            result["notes"].append(
                "low_body_battery"
            )

    # =================================================
    # HIGH STRESS
    # =================================================

    if stress is not None:

        if stress >= 75:

            result["support_mode"] = True

            result["notes"].append(
                "high_physiological_stress"
            )

    # =================================================
    # LOW SLEEP
    # =================================================

    if sleep is not None:

        if sleep <= 40:

            result["notes"].append(
                "poor_sleep_recovery"
            )

    return result


# =====================================================
# SUMMARY
# =====================================================

def summarize_physiology(state):

    if not isinstance(state, dict):

        return "invalid physiology"

    return (

        f"battery={state.get('body_battery')} | "

        f"stress={state.get('stress_score')} | "

        f"sleep={state.get('sleep_score')} | "

        f"hr={state.get('heart_rate')}"

    )
