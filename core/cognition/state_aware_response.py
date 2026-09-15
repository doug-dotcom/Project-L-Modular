"""Project L Layer 8: bounded state-aware response shaping.

The layer adapts response style only from explicit current-turn language and
non-sensitive interaction state already present in working memory. It never
diagnoses, labels, stores, or treats an inferred internal state as fact.
"""

from __future__ import annotations

import re


STATE_AWARE_VERSION = "1.0"


def _has(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal in text for signal in signals)


def _profile(message: str, working_memory: dict | None) -> tuple[str, str, float]:
    text = " ".join(str(message or "").lower().split())
    phase = str((working_memory or {}).get("conversation_phase") or "")

    # Explicit user language outranks inferred interaction phase.
    if _has(text, (
        "i'm overwhelmed", "im overwhelmed", "feeling overwhelmed",
        "too much", "keep it simple", "make it simple", "one thing at a time",
        "short answer", "just the basics", "my head is full", "can't process",
        "cant process",
    )):
        return "low_load", "Doug explicitly asked for reduced cognitive load.", 1.0

    if _has(text, (
        "i'm reflecting", "im reflecting", "feeling reflective", "let me think",
        "help me unpack", "help me understand myself", "what do you make of this",
        "what does this mean for me", "sit with this", "talk this through",
    )):
        return "reflective", "Doug explicitly used reflective or meaning-making language.", 0.95

    if _has(text, (
        "i'm excited", "im excited", "let's smash", "lets smash", "let's go",
        "lets go", "keep building", "go go go", "i'm pumped", "im pumped",
    )):
        return "energised", "Doug explicitly signalled high engagement or momentum.", 0.95

    if _has(text, (
        "just do it", "get it done", "fix it", "build it", "go", "next go",
        "keep going", "deploy it", "ship it",
    )) or phase == "execution":
        return "task_focused", "Current interaction is explicitly execution-focused.", 0.85

    if phase == "planning":
        return "planning", "Working memory marks the current interaction as planning.", 0.75

    if phase == "review":
        return "review", "Working memory marks the current interaction as review.", 0.75

    return "neutral", "No strong current-turn response-shaping signal was established.", 0.5


def build_state_aware_response_packet(message: str, working_memory: dict | None) -> dict:
    profile, basis, confidence = _profile(message, working_memory)

    instructions = {
        "low_load": (
            "Reduce cognitive load: answer directly, use short sections, prioritise one next step, "
            "avoid optional branches unless Doug asks for them."
        ),
        "reflective": (
            "Use a calm reflective cadence. Preserve nuance, distinguish observation from interpretation, "
            "and ask at most one useful question only if it genuinely advances reflection."
        ),
        "energised": (
            "Match the momentum without becoming reckless: be concise, energetic and action-oriented, "
            "while preserving evidence and safety boundaries."
        ),
        "task_focused": (
            "Lead with the result or next executable step. Minimise background explanation unless it changes the decision."
        ),
        "planning": (
            "Structure choices and dependencies clearly. Prefer a recommended path plus bounded alternatives when useful."
        ),
        "review": (
            "Lead with status, what worked, what failed, and the next correction. Avoid re-explaining settled background."
        ),
        "neutral": (
            "Use L's normal warm, grounded style. Do not invent an emotional or cognitive state from sparse cues."
        ),
    }

    return {
        "engine": "state_aware_response_layer",
        "version": STATE_AWARE_VERSION,
        "active": profile != "neutral",
        "response_profile": profile,
        "confidence": confidence,
        "basis": basis,
        "instruction": instructions[profile],
        "governance": {
            "current_turn_only": True,
            "durable_memory_write": False,
            "diagnosis_or_clinical_label": False,
            "hidden_state_claims_prohibited": True,
            "explicit_user_language_outranks_inference": True,
            "style_adaptation_only": True,
        },
    }


__all__ = ["STATE_AWARE_VERSION", "build_state_aware_response_packet"]
