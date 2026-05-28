# =====================================================
# PROJECT L — SALIENCE ENGINE
# AODS-4G-01
#
# Purpose:
# Adds importance scoring to existing cognition flow.
# Does NOT replace memory, Connie, Tegan, Ellie, or retrieval.
# This is a spoke added to the existing wheel.
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


def extract_memory_text(item):
    if item is None:
        return ""

    if isinstance(item, str):
        return item.lower()

    if not isinstance(item, dict):
        return str(item).lower()

    parts = []

    keys = [
        "content",
        "summary",
        "text",
        "memory",
        "message",
        "title",
        "domain",
        "memory_type",
        "tags"
    ]

    for key in keys:
        value = item.get(key)

        if isinstance(value, list):
            parts.append(" ".join(str(v) for v in value))
        elif value is not None:
            parts.append(str(value))

    return " ".join(parts).lower()


def infer_salience_factors(item, runtime_state=None):
    if not isinstance(item, dict):
        item = {"content": str(item)}

    text = extract_memory_text(item)

    emotional = _safe_float(item.get("emotional_weight", 0.0))
    identity = _safe_float(item.get("identity_weight", 0.0))
    goal = _safe_float(item.get("goal_weight", 0.0))
    recency = _safe_float(item.get("recency_weight", 0.0))
    repetition = _safe_float(item.get("repetition_weight", 0.0))

    memory_type = str(item.get("memory_type", "")).lower()
    domain = str(item.get("domain", "")).lower()

    if memory_type in ["identity", "core_identity"]:
        identity = max(identity, 0.90)

    if memory_type in ["emotional", "health", "mental_health"]:
        emotional = max(emotional, 0.75)

    if memory_type in ["procedural", "instruction", "rule"]:
        goal = max(goal, 0.75)

    if domain in ["identity", "family", "health", "legal", "project_l", "dva"]:
        identity = max(identity, 0.65)

    if any(word in text for word in [
        "today",
        "tonight",
        "current",
        "now",
        "latest",
        "just happened"
    ]):
        recency = max(recency, 0.60)

    if any(word in text for word in [
        "always",
        "recurring",
        "pattern",
        "trigger",
        "again"
    ]):
        repetition = max(repetition, 0.55)

    if any(word in text for word in [
        "scared",
        "unsafe",
        "nightmare",
        "ptsd",
        "panic",
        "overwhelmed",
        "mental health"
    ]):
        emotional = max(emotional, 0.75)

    if any(word in text for word in [
        "project l",
        "truth mode",
        "connie",
        "tegan",
        "brittany",
        "ellie",
        "memory",
        "cognition",
        "salience",
        "architecture"
    ]):
        goal = max(goal, 0.70)

    runtime_state = runtime_state or {}

    physiology_state = (
        physiology_state or {}
    )

    stress = _safe_float(runtime_state.get("stress_level", 0.0))
    cognitive_load = _safe_float(runtime_state.get("cognitive_load", 0.0))

    body_battery = physiology_state.get(
        "body_battery"
    )

    physiological_stress = physiology_state.get(
        "stress_score"
    )

    sleep_score = physiology_state.get(
        "sleep_score"
    )

    if stress >= 0.70:
        emotional = max(emotional, 0.80)

    if cognitive_load >= 0.70:
        goal = max(goal, 0.75)

    # =================================================
    # PHYSIOLOGY SALIENCE MODULATION
    # =================================================

    physiology_salience_boost = 0.0

    if body_battery is not None:

        if body_battery <= 20:

            emotional = max(emotional, 0.80)

            physiology_salience_boost += 0.08

        elif body_battery >= 80:

            goal = max(goal, 0.80)

            physiology_salience_boost += 0.05

    if physiological_stress is not None:

        if physiological_stress >= 75:

            emotional = max(emotional, 0.85)

            physiology_salience_boost += 0.10

    if sleep_score is not None:

        if sleep_score <= 40:

            emotional = max(emotional, 0.75)

            physiology_salience_boost += 0.05

    return {
        "emotional": _clamp(emotional),
        "identity": _clamp(identity),
        "goal": _clamp(goal),
        "recency": _clamp(recency),
        "repetition": _clamp(repetition),

        "physiology_boost": _clamp(
            physiology_salience_boost,
            0.0,
            0.25
        )
    }


def keyword_boost(text):
    text = str(text).lower()

    terms = {
        "children": 0.08,
        "family": 0.08,
        "ptsd": 0.08,
        "mental health": 0.08,
        "truth mode": 0.08,
        "project l": 0.08,
        "identity": 0.07,
        "safety": 0.07,
        "medication": 0.07,
        "dva": 0.07,
        "legal": 0.07,
        "capstone": 0.07,
        "shine": 0.06,
        "memory": 0.06,
        "connie": 0.06,
        "tegan": 0.06,
        "brittany": 0.06,
        "ellie": 0.06,
        "salience": 0.06,
        "cognition": 0.06
    }

    boost = 0.0

    for term, weight in terms.items():
        if term in text:
            boost += weight

    return _clamp(boost, 0.0, 0.25)


def score_salience(

    item,

    runtime_state=None,

    physiology_state=None

):
    if item is None:
        return 0.0

    text = extract_memory_text(item)

    factors = infer_salience_factors(
        item if isinstance(item, dict) else {"content": str(item)},
        runtime_state=runtime_state
    )

    score = 0.0
    score += factors["emotional"] * 0.27
    score += factors["identity"] * 0.25
    score += factors["goal"] * 0.22
    score += factors["recency"] * 0.14
    score += factors["repetition"] * 0.08
    score += keyword_boost(text) * 0.04
    score += factors["physiology_boost"] * 0.10

    return round(_clamp(score), 3)


def annotate_salience(item, runtime_state=None):
    if isinstance(item, dict):
        out = dict(item)
    else:
        out = {"content": str(item)}

    out["salience_score"] = score_salience(
        out,
        runtime_state=runtime_state
    )

    out["salience_engine"] = "AODS-4G-01"

    return out


def sort_by_salience(items, runtime_state=None, limit=None):
    if not isinstance(items, list):
        return []

    ranked = []

    for item in items:
        ranked.append(
            annotate_salience(
                item,
                runtime_state=runtime_state
            )
        )

    ranked.sort(
        key=lambda x: x.get("salience_score", 0.0),
        reverse=True
    )

    if limit is not None:
        try:
            ranked = ranked[:int(limit)]
        except Exception:
            pass

    return ranked


def build_salience_context(items, runtime_state=None, limit=8):
    ranked = sort_by_salience(
        items,
        runtime_state=runtime_state,
        limit=limit
    )

    lines = []

    for item in ranked:
        content = str(
            item.get("content")
            or item.get("summary")
            or item.get("text")
            or ""
        ).strip()

        if len(content) > 220:
            content = content[:220] + "..."

        lines.append(
            f"[salience={item.get('salience_score')}] {content}"
        )

    return "\n".join(lines)

