"""Project L Layer 11 + 14: cue-driven memory with saturation control.

The present turn may justify a bounded memory probe without Doug explicitly
asking L to recall anything. Layer 14 prevents ordinary conversation from
triggering repeated near-identical probes. Retrieval remains separate from
publication authority.
"""

from __future__ import annotations

import re

from core.cognition.associative_saturation import AssociativeRetrievalGovernor


CUE_DRIVEN_MEMORY_VERSION = "1.1"
_ASSOCIATIVE_GOVERNOR = AssociativeRetrievalGovernor()
_ASSOCIATIVE_SCOPE = "doug_global_associative"

_RECURRENCE = (
    "again", "same thing", "same feeling", "same pattern", "like before",
    "similar to before", "this reminds me", "reminds me of", "keeps happening",
    "keeps coming up", "another time", "here we go again", "back in this place",
)
_DECISION_LESSON = (
    "i decided", "we decided", "i chose", "we chose", "i learned", "i learnt",
    "i realised", "i realized", "lesson", "worked before", "didn't work before",
    "did not work before", "what helped", "what worked",
)
_PERSONAL_DOMAINS = (
    "family", "daughter", "son", "kids", "children", "friend", "relationship",
    "sponsor", "meeting", "recovery", "sober", "sobriety", "sleep", "health",
    "doctor", "physio", "gym", "hockey", "dive", "diving", "travel", "money",
    "finance", "project", "work", "pauline",
)
_EXPERIENCE_WORDS = (
    "feel", "feeling", "felt", "worried", "worry", "thinking", "thought",
    "noticed", "notice", "happened", "happening", "struggling", "stuck",
    "excited", "relaxed", "peaceful", "angry", "sad", "happy", "guilty",
    "guilt", "afraid", "scared", "overwhelmed", "calm", "proud",
)
_GENERIC = re.compile(
    r"^(?:hi|hello|hey|thanks|thank you|ok|okay|yep|yes|no|nope|cool|awesome|go)[\s.!👊👍🙏🥳😂]*$",
    re.I,
)
_DIRECT_QUESTION = re.compile(
    r"^(?:who|what|when|where|why|how|can|could|should|would|do|does|did|is|are|was|were)\b",
    re.I,
)


def _normalise(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def reset_associative_cue_state() -> None:
    """Reset process-only saturation state. Intended for tests/runtime recovery."""
    _ASSOCIATIVE_GOVERNOR.reset(_ASSOCIATIVE_SCOPE)


def assess_present_cue(message: str) -> dict:
    """Score and govern whether an ordinary turn deserves a memory probe.

    Explicit recall is handled independently by the cognitive controller and is
    never dependent on this result. This path applies only to associative recall.
    """
    raw = _normalise(message)
    text = raw.casefold()
    words = re.findall(r"[a-z0-9']+", text)
    reasons: list[str] = []
    score = 0.0

    if not raw or _GENERIC.fullmatch(raw) or len(words) < 4:
        return {
            "engine": "cue_driven_external_memory",
            "version": CUE_DRIVEN_MEMORY_VERSION,
            "should_retrieve": False,
            "raw_should_retrieve": False,
            "score": 0.0,
            "reasons": [],
            "saturation": {"applies": False, "allowed": True, "reason": "no_material_cue"},
        }

    recurrence = [item for item in _RECURRENCE if item in text]
    if recurrence:
        score += 0.62
        reasons.append("recurrence_or_association")

    decision_lesson = [item for item in _DECISION_LESSON if item in text]
    if decision_lesson:
        score += 0.48
        reasons.append("decision_or_lesson_cue")

    self_reference = bool(re.search(r"\b(?:i|i'm|i’ve|i've|me|my|mine)\b", text))
    experience = any(re.search(rf"\b{re.escape(word)}\b", text) for word in _EXPERIENCE_WORDS)
    domain = any(re.search(rf"\b{re.escape(word)}\b", text) for word in _PERSONAL_DOMAINS)
    if self_reference and experience:
        score += 0.34
        reasons.append("first_person_experience")
    if self_reference and domain:
        score += 0.28
        reasons.append("personal_domain_context")

    names = re.findall(r"\b[A-Z][a-z]{2,}\b", raw)
    first_word = raw.split(" ", 1)[0].strip(".,!?;:") if raw else ""
    proper_names = [name for name in names if name != first_word]
    if self_reference and proper_names:
        score += 0.22
        reasons.append("named_person_or_place")

    if _DIRECT_QUESTION.match(text) and not recurrence:
        score = max(0.0, score - 0.25)
        reasons.append("direct_question_penalty")

    score = round(min(1.0, score), 2)
    raw_should_retrieve = score >= 0.55
    saturation = (
        _ASSOCIATIVE_GOVERNOR.evaluate_cue(
            _ASSOCIATIVE_SCOPE,
            raw,
            score,
        )
        if raw_should_retrieve
        else {"applies": False, "allowed": True, "reason": "below_cue_threshold"}
    )
    should_retrieve = bool(raw_should_retrieve and saturation.get("allowed", True))
    if raw_should_retrieve and not should_retrieve:
        reasons.append("saturation_suppressed")

    return {
        "engine": "cue_driven_external_memory",
        "version": CUE_DRIVEN_MEMORY_VERSION,
        "should_retrieve": should_retrieve,
        "raw_should_retrieve": raw_should_retrieve,
        "score": score,
        "reasons": reasons,
        "saturation": saturation,
    }


def build_cue_memory_packet(
    message: str,
    cognitive_plan: dict | None,
    rhee_packet: dict | None,
    confidence_evidence: dict | None,
) -> dict:
    """Build the governed post-retrieval cue packet used by L's synthesis."""
    plan = cognitive_plan or {}
    needs = plan.get("needs") or {}
    cue = plan.get("associative_cue") or assess_present_cue(message)
    associative_only = bool(needs.get("cue_driven_memory"))
    rhee = rhee_packet or {}
    evidence = list(rhee.get("evidence") or [])
    permissions = (confidence_evidence or {}).get("claim_permissions") or {}
    retrieved = bool(rhee.get("recall_active") and evidence)

    strong_surface_basis = bool(
        retrieved
        and float(cue.get("score") or 0.0) >= 0.75
        and (permissions.get("personal_fact") or permissions.get("supported_inference"))
    )

    return {
        "engine": "cue_driven_external_memory",
        "version": CUE_DRIVEN_MEMORY_VERSION,
        "active": associative_only,
        "cue": cue,
        "saturation": cue.get("saturation") or {},
        "retrieval_attempted": associative_only,
        "retrieval_found_evidence": retrieved,
        "evidence_count": len(evidence),
        "silent_use_allowed": retrieved,
        "surface_candidate": strong_surface_basis,
        "instruction": (
            "Treat the present turn as an associative retrieval cue. Retrieved memory may inform "
            "your reasoning silently. Surface a memory only when it materially improves the present "
            "answer and is relevant, sufficiently supported, current enough, proportionate and not "
            "needlessly intimate. Retrieval is never publication authority. If the memory is weak, "
            "outdated, tangential, overly intimate or unnecessary, discard it. Never announce that "
            "an associative memory search occurred unless Doug asks. Preserve Doug's agency and make "
            "memory feel like being known, not watched."
            if associative_only else
            "No cue-driven memory probe was required for this turn."
        ),
        "governance": {
            "retrieval_requires_explicit_recall_command": False,
            "retrieval_equals_surface_permission": False,
            "background_retrieval_rate_limited": True,
            "explicit_recall_never_throttled": True,
            "provenance_required": True,
            "confidence_required": True,
            "recency_considered": True,
            "privacy_required": True,
            "agency_required": True,
            "silent_discard_allowed": True,
            "surface_only_if_materially_useful": True,
        },
    }


__all__ = [
    "CUE_DRIVEN_MEMORY_VERSION",
    "assess_present_cue",
    "build_cue_memory_packet",
    "reset_associative_cue_state",
]
