# =====================================================
# AODS 1 - RONNIE REFLECTOR
# THE LEARNING LOOPERS
# =====================================================

from datetime import datetime


def _safe_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _split_sentences(text):
    text = _safe_text(text)
    if not text:
        return []

    rough = (
        text.replace("!", ".")
            .replace("?", ".")
            .replace("\n", ".")
            .split(".")
    )

    return [s.strip() for s in rough if s.strip()]


def _find_standout_points(text, limit=5):
    sentences = _split_sentences(text)

    keywords = [
        "realised", "realized", "noticed", "felt", "important",
        "stuck", "changed", "learned", "grief", "love",
        "keys", "trust", "protect", "agency", "reflection",
        "meaning", "pauline", "mum", "dad"
    ]

    scored = []

    for sentence in sentences:
        score = 0
        lower = sentence.lower()

        for word in keywords:
            if word in lower:
                score += 1

        if len(sentence) > 80:
            score += 1

        if score > 0:
            scored.append((score, sentence))

    scored.sort(key=lambda x: x[0], reverse=True)

    selected = [item[1] for item in scored[:limit]]

    if not selected:
        selected = sentences[:limit]

    return selected


def _find_emotional_observations(text):
    lower = _safe_text(text).lower()

    observations = []

    emotion_map = {
        "grief": ["grief", "leaking", "cry", "tears", "lost"],
        "love": ["love", "loved", "proud", "beautiful boy"],
        "confidence": ["confidence", "capable", "trust myself", "keys"],
        "humour": ["lol", "😂", "🤣", "funny", "joke"],
        "protection": ["protect", "protector", "safe", "capable"],
        "curiosity": ["wonder", "interesting", "what if", "why"]
    }

    for label, markers in emotion_map.items():
        if any(marker in lower for marker in markers):
            observations.append(label)

    return observations


def _find_unresolved_items(text):
    lower = _safe_text(text).lower()

    unresolved = []

    if "not sure" in lower or "i am not sure" in lower:
        unresolved.append("Uncertainty present")

    if "wonder" in lower:
        unresolved.append("Open curiosity present")

    if "?" in text:
        unresolved.append("Question remains open")

    if "need to" in lower or "should" in lower:
        unresolved.append("Possible next-step tension present")

    return unresolved


def run_ronnie_reflector(
    experience,
    processed_meaning=None,
    identity_context=None,
    memory_context=None,
    emotional_context=None,
    values_context=None
):
    """
    Ronnie Reflector

    Ronnie only reflects.
    Ronnie does not create lessons.
    Ronnie does not create adjustments.
    Ronnie does not give advice.
    """

    experience = _safe_text(experience)
    processed_meaning = _safe_text(processed_meaning)

    combined = "\n".join(
        part for part in [
            experience,
            processed_meaning,
            _safe_text(identity_context),
            _safe_text(memory_context),
            _safe_text(emotional_context),
            _safe_text(values_context)
        ]
        if part
    )

    standout_points = _find_standout_points(combined)
    emotional_observations = _find_emotional_observations(combined)
    unresolved_items = _find_unresolved_items(combined)

    reflection = {
        "agent": "Ronnie Reflector",
        "team": "Learning Loopers",
        "aods": "AODS 1",
        "role": "Reflector",
        "timestamp": datetime.utcnow().isoformat() + "Z",

        "what_happened": experience,
        "what_stood_out": standout_points,
        "what_felt_important": emotional_observations,
        "what_am_i_still_thinking_about": unresolved_items,

        "rules_applied": [
            "Observed without solving",
            "Reflected without teaching",
            "Avoided lesson creation",
            "Avoided adjustment creation",
            "Remained curious"
        ],

        "next_agent": "Finlay Finder"
    }

    return reflection


if __name__ == "__main__":
    test = """
    Doug noticed that he kept looking to Pauline for validation.
    He realised this connected to mentors, Dad, Sean Graham and Walshy.
    The keys metaphor stood out.
    """

    result = run_ronnie_reflector(test)

    import json
    print(json.dumps(result, indent=2))
