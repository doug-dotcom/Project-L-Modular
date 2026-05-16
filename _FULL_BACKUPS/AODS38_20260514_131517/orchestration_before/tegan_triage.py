# ============================================================
# MAJOR TEGAN TRIAGE
# Operational orchestration layer for Shine L
# ============================================================

from orchestration.agent_registry import (
    get_active_captains,
)

from orchestration.meta_suppression import (
    suppress_agent_routing,
)

from orchestration.weighted_scoring import (
    score_cognition_domains,
    calculate_agent_confidence,
)


def assess_urgency(message: str):

    text = message.lower()

    high_terms = [
        "urgent",
        "panic",
        "overwhelmed",
        "broken",
        "can't lose",
        "asap",
        "emergency",
        "not working",
        "comms are down"
    ]

    medium_terms = [
        "confused",
        "stuck",
        "issue",
        "problem",
        "help",
        "fix",
        "drift"
    ]

    for term in high_terms:
        if term in text:
            return "high"

    for term in medium_terms:
        if term in text:
            return "medium"

    return "normal"


def select_primary_captain(message: str):

    cognition_scores = score_cognition_domains(message)
    agent_scores = calculate_agent_confidence(message)

    combined = {}

    for name, score in cognition_scores.items():
        combined[name] = combined.get(name, 0) + score

    for name, score in agent_scores.items():
        combined[name] = combined.get(name, 0) + score

    if not combined:
        return None

    ranked = sorted(
        combined.items(),
        key=lambda item: item[1],
        reverse=True
    )

    top_name, top_score = ranked[0]

    if top_score <= 0:
        return None

    return {
        "captain": top_name,
        "score": top_score,
        "ranked": ranked
    }


def triage_message(message: str):

    suppressed = suppress_agent_routing(message)

    urgency = assess_urgency(message)

    primary = None

    if not suppressed:
        primary = select_primary_captain(message)

    active_captains = get_active_captains()

    result = {
        "triage_officer": "Major Tegan Triage",
        "urgency": urgency,
        "suppressed": suppressed,
        "primary_captain": primary,
        "active_captain_count": len(active_captains),
        "doctrine": "Tegan filters signal, allocates captains, and protects L from command overload."
    }

    return result


def build_tegan_triage_report(message: str):

    result = triage_message(message)

    lines = []
    lines.append("MAJOR TEGAN TRIAGE REPORT")
    lines.append("")
    lines.append("Urgency: " + str(result.get("urgency")))
    lines.append("Suppressed: " + str(result.get("suppressed")))

    primary = result.get("primary_captain")

    if primary:
        lines.append(
            "Primary Captain: "
            + str(primary.get("captain"))
            + " | Score: "
            + str(primary.get("score"))
        )
    else:
        lines.append("Primary Captain: L direct response")

    lines.append("")
    lines.append(result.get("doctrine"))

    return "\n".join(lines)
