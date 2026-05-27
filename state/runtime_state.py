# =====================================================
# PROJECT L — RUNTIME STATE
# AODS-4G-02
#
# Purpose:
# Gives L a live cognition state.
# This does NOT replace orchestration.
# It feeds state-awareness into existing systems.
# =====================================================

from datetime import datetime
from zoneinfo import ZoneInfo


DEFAULT_STATE = {

    "emotional_state": "neutral",

    "stress_level": 0.30,

    "emotional_load": 0.30,

    "cognitive_load": 0.30,

    "conversation_depth": 0.30,

    "conversation_momentum": 0.30,

    "truth_mode_intensity": 0.70,

    "active_focus": None,

    "active_projects": []
}


# =====================================================
# SAFE FLOAT
# =====================================================

def _safe_float(value, default=0.0):

    try:
        return float(value)

    except Exception:
        return default


# =====================================================
# CLAMP
# =====================================================

def _clamp(value, low=0.0, high=1.0):

    value = _safe_float(value, low)

    if value < low:
        return low

    if value > high:
        return high

    return value


# =====================================================
# BUILD RUNTIME STATE
# =====================================================

def build_runtime_state(

    user_message="",

    retrieved_rows=None,

    active_projects=None

):

    state = dict(DEFAULT_STATE)

    text = str(user_message).lower()

    # =================================================
    # TIMESTAMP
    # =================================================

    state["timestamp"] = str(

        datetime.now(

            ZoneInfo("Australia/Brisbane")

        )

    )

    # =================================================
    # PROJECTS
    # =================================================

    if active_projects:

        state["active_projects"] = active_projects

    # =================================================
    # EMOTIONAL LOAD
    # =================================================

    emotional_terms = [

        "scared",
        "panic",
        "unsafe",
        "nightmare",
        "triggered",
        "ptsd",
        "stress",
        "overwhelmed",
        "mental health",
        "anxiety"

    ]

    for term in emotional_terms:

        if term in text:

            state["emotional_load"] += 0.10
            state["stress_level"] += 0.08

    # =================================================
    # COGNITIVE LOAD
    # =================================================

    cognition_terms = [

        "project l",
        "cognition",
        "architecture",
        "memory",
        "salience",
        "truth mode",
        "orchestration",
        "compression",
        "connie",
        "tegan"

    ]

    for term in cognition_terms:

        if term in text:

            state["cognitive_load"] += 0.07
            state["conversation_depth"] += 0.05

    # =================================================
    # MOMENTUM
    # =================================================

    if retrieved_rows:

        try:

            count = len(retrieved_rows)

            state["conversation_momentum"] += (

                min(count / 20, 0.50)

            )

        except Exception:

            pass

    # =================================================
    # ACTIVE FOCUS
    # =================================================

    if "project l" in text:

        state["active_focus"] = "project_l"

    elif "mental health" in text:

        state["active_focus"] = "mental_health"

    elif "dva" in text:

        state["active_focus"] = "dva"

    elif "family" in text:

        state["active_focus"] = "family"

    # =================================================
    # CLAMP VALUES
    # =================================================

    for key in [

        "stress_level",
        "emotional_load",
        "cognitive_load",
        "conversation_depth",
        "conversation_momentum",
        "truth_mode_intensity"

    ]:

        state[key] = _clamp(state[key])

    return state


# =====================================================
# SUMMARY
# =====================================================

def summarize_runtime_state(state):

    if not isinstance(state, dict):

        return "invalid runtime state"

    return (

        f"focus={state.get('active_focus')} | "

        f"stress={state.get('stress_level')} | "

        f"emotion={state.get('emotional_load')} | "

        f"cognitive={state.get('cognitive_load')} | "

        f"depth={state.get('conversation_depth')}"

    )
