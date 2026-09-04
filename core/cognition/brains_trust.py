"""Project L's Brains Trust as governed cognitive lenses.

The Brains Trust is a reasoning framework, not a collection of autonomous
personalities.  RIKE selects only the lenses relevant to the current request.
"""

from __future__ import annotations


LENSES = {
    "evidence": {
        "purpose": "Separate observations, sourced facts and inference.",
        "question": "What is directly supported, contradicted or still unknown?",
        "signals": ("evidence", "fact", "prove", "source", "verify", "true"),
    },
    "systems": {
        "purpose": "Examine relationships, feedback loops and downstream effects.",
        "question": "What interacts with this and what changes downstream?",
        "signals": ("system", "pattern", "cause", "effect", "impact", "architecture"),
    },
    "decision": {
        "purpose": "Compare options against goals, constraints and trade-offs.",
        "question": "Which option is best supported under the stated constraints?",
        "signals": ("compare", "decide", "option", "choose", "should", "trade-off", "recommend"),
    },
    "longitudinal": {
        "purpose": "Test whether a claimed pattern is supported across time.",
        "question": "Has this repeated, changed, strengthened or weakened?",
        "signals": ("again", "history", "over time", "pattern", "growth", "changed"),
    },
    "human": {
        "purpose": "Account for behaviour, emotion, cognition and lived context.",
        "question": "What human needs, limits or behaviours materially affect this?",
        "signals": ("feel", "behaviour", "emotion", "trauma", "relationship", "overwhelm"),
    },
    "uncertainty": {
        "purpose": "Calibrate confidence and identify what could change the conclusion.",
        "question": "How certain is this and what evidence would alter the result?",
        "signals": ("risk", "uncertain", "confidence", "likely", "forecast", "predict"),
    },
    "cognition": {
        "purpose": "Account for attention, executive function, cognitive load and bias.",
        "question": "What cognitive limits or biases could distort this judgement?",
        "signals": ("attention", "bias", "cognitive", "focus", "overload", "executive function"),
    },
    "feedback": {
        "purpose": "Examine feedback, adaptation, control and course correction.",
        "question": "What feedback would reveal drift and permit correction?",
        "signals": ("adapt", "feedback", "learn", "loop", "correct", "drift"),
    },
    "complexity": {
        "purpose": "Avoid false certainty in nonlinear or emerging situations.",
        "question": "Which interactions make the outcome nonlinear or hard to predict?",
        "signals": ("complex", "emerge", "network", "nonlinear", "uncertain system"),
    },
}


def select_lenses(message: str, limit: int = 4) -> list[dict]:
    text = str(message or "").lower()
    selected = []

    for name, lens in LENSES.items():
        if any(signal in text for signal in lens["signals"]):
            selected.append({
                "name": name,
                "purpose": lens["purpose"],
                "question": lens["question"],
            })

    if not selected:
        selected.append({
            "name": "evidence",
            "purpose": LENSES["evidence"]["purpose"],
            "question": LENSES["evidence"]["question"],
        })

    return selected[: max(1, int(limit))]
