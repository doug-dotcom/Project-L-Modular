"""Deterministic metacognitive planning for Project L.

The controller plans cognition before retrieval or model generation. It does not
answer Doug, infer personal facts, or call tools; it only declares which bounded
systems a request has earned.
"""

from __future__ import annotations

import re

from core.cognition.decision_memory import decision_recall_requested
from core.cognition.relationship_intelligence import relationship_query_requested
from core.cognition.rike import needs_structured_reasoning


CONTROLLER_VERSION = "1.4"


def _has(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal in text for signal in signals)


def _continuity_signal(text: str) -> bool:
    """Detect turns whose meaning depends on a previously active thread."""
    if not text:
        return False
    if re.fullmatch(
        r"(?:go|next\s+go|go\s+again|keep\s+going|continue|carry\s+on|resume|pick\s+it\s+up|"
        r"let'?s\s+keep\s+going|let'?s\s+continue)[\s.!👊👍🥳😂🙏]*",
        text,
        flags=re.IGNORECASE,
    ):
        return True
    return _has(text, (
        "pick up where we left off",
        "where we left off",
        "where were we",
        "what were we doing",
        "continue from before",
        "continue from last time",
        "keep building",
        "keep working on",
        "back to what we were doing",
        "resume the last",
        "resume our",
        "next layer",
        "another layer",
    ))


def _life_pattern_signal(text: str) -> bool:
    """Detect requests to connect recurring themes across Doug's life domains."""
    return _has(text, (
        "what have you noticed",
        "what are you noticing",
        "what do you notice",
        "join the dots",
        "connect the dots",
        "recurring theme",
        "recurring themes",
        "common thread",
        "common threads",
        "what tends to happen",
        "keeps happening",
        "keeps coming up",
        "what keeps coming up",
        "across my life",
        "across my health",
        "across recovery",
        "across my recovery",
        "across my projects",
        "across family",
        "across my family",
        "life pattern",
        "life patterns",
        "bigger picture",
        "how things connect",
        "how these things connect",
        "connections between",
        "themes in my life",
        "themes lately",
    ))


def plan_cognition(message: str) -> dict:
    """Return an inspectable, fail-closed plan without invoking any specialist."""
    raw_text = str(message or "").strip()
    text = " ".join(raw_text.lower().split())

    continuity_signal = _continuity_signal(text)
    life_pattern_signal = _life_pattern_signal(text)
    decision_signal = decision_recall_requested(text)
    relationship_signal = relationship_query_requested(raw_text)
    recall_signal = continuity_signal or life_pattern_signal or decision_signal or relationship_signal or _has(text, (
        "remember", "recall", "deep recall", "what do you know", "tell me about my",
        "my recovery", "my family", "my history", "my journey", "my project",
        "we discussed", "we decided", "we built", "earlier", "last time", "again",
        "still", "continue", "update it", "same as before", "our plan", "our project",
    ))
    longitudinal_signal = life_pattern_signal or _has(text, (
        "pattern", "over time", "timeline", "changed", "progress", "last six months",
        "last 6 months", "weekly report", "report for pauline", "journey",
    ))
    current_evidence_signal = _has(text, (
        "latest", "current", "today's", "today’s", "news", "research", "look up",
        "search", "verify online", "weather", "market", "price", "schedule",
        "email", "gmail", "calendar", "tasks", "transactions", "bank statement",
    ))
    action_signal = bool(re.search(
        r"\b(?:send|delete|create|schedule|book|upload|download|add|remove|cancel)\b",
        text,
    ))
    structured = needs_structured_reasoning(text) or longitudinal_signal
    high_stakes = _has(text, (
        "medical", "diagnosis", "legal", "insurance claim", "tpd", "financial advice",
        "suicide", "self-harm", "overdose", "emergency",
    ))

    if action_signal:
        problem_type = "action"
    elif life_pattern_signal:
        problem_type = "life_pattern"
    elif decision_signal:
        problem_type = "decision_recall"
    elif relationship_signal:
        problem_type = "relationship_intelligence"
    elif longitudinal_signal:
        problem_type = "longitudinal"
    elif recall_signal:
        problem_type = "personal_recall"
    elif current_evidence_signal:
        problem_type = "external_evidence"
    elif structured:
        problem_type = "analysis"
    else:
        problem_type = "conversation"

    substantial = problem_type != "conversation" or len(text.split()) >= 18
    memory_required = recall_signal or longitudinal_signal
    external_evidence_required = current_evidence_signal or high_stakes
    difficulty_score = sum((substantial, structured, longitudinal_signal, high_stakes, action_signal, life_pattern_signal, decision_signal, relationship_signal))
    difficulty = "high" if difficulty_score >= 3 else "medium" if difficulty_score >= 1 else "low"

    known = []
    unknown = []
    if memory_required:
        unknown.append("relevant_personal_evidence_until_retrieved")
    else:
        known.append("personal_memory_not_required")
    if continuity_signal:
        unknown.append("prior_thread_until_retrieved")
    if life_pattern_signal:
        unknown.append("cross_domain_pattern_evidence_until_retrieved")
    if decision_signal:
        unknown.append("decision_rationale_until_retrieved")
    if relationship_signal:
        unknown.append("relationship_evidence_until_retrieved")
    if external_evidence_required:
        unknown.append("current_external_facts_until_capability_returns")
    else:
        known.append("external_evidence_not_required")

    return {
        "engine": "l_cognitive_controller",
        "version": CONTROLLER_VERSION,
        "principle": "complexity_earns_cognition",
        "problem_type": problem_type,
        "difficulty": difficulty,
        "substantial": substantial,
        "known": known,
        "unknown": unknown,
        "needs": {
            "memory": memory_required,
            "external_evidence": external_evidence_required,
            "structured_reasoning": structured or high_stakes,
            "longitudinal_reasoning": longitudinal_signal,
            "continuity": continuity_signal,
            "life_pattern": life_pattern_signal,
            "decision_memory": decision_signal,
            "relationship_intelligence": relationship_signal,
            "specialist": external_evidence_required or action_signal,
        },
        "signals": {
            "recall": recall_signal,
            "continuity": continuity_signal,
            "life_pattern": life_pattern_signal,
            "decision_memory": decision_signal,
            "relationship_intelligence": relationship_signal,
            "longitudinal": longitudinal_signal,
            "current_evidence": current_evidence_signal,
            "action": action_signal,
            "high_stakes": high_stakes,
        },
    }


def finalise_cognition_plan(plan: dict, rhee_packet: dict, capability_packet: dict) -> dict:
    """Record what became known after authorised retrieval/capability execution."""
    result = {**(plan or {})}
    result["known"] = list(result.get("known") or [])
    result["unknown"] = list(result.get("unknown") or [])
    if result.get("needs", {}).get("memory"):
        marker = "relevant_personal_evidence_until_retrieved"
        if (rhee_packet or {}).get("recall_active"):
            result["known"].append("personal_evidence_retrieved")
            result["unknown"] = [item for item in result["unknown"] if item != marker]
            if result.get("needs", {}).get("continuity"):
                result["known"].append("prior_thread_evidence_retrieved")
                result["unknown"] = [item for item in result["unknown"] if item != "prior_thread_until_retrieved"]
            if result.get("needs", {}).get("life_pattern"):
                result["known"].append("pattern_candidate_evidence_retrieved")
                result["unknown"] = [item for item in result["unknown"] if item != "cross_domain_pattern_evidence_until_retrieved"]
            if result.get("needs", {}).get("decision_memory"):
                result["known"].append("decision_evidence_retrieved")
                result["unknown"] = [item for item in result["unknown"] if item != "decision_rationale_until_retrieved"]
            if result.get("needs", {}).get("relationship_intelligence"):
                result["known"].append("relationship_evidence_retrieved")
                result["unknown"] = [item for item in result["unknown"] if item != "relationship_evidence_until_retrieved"]
        else:
            result["unknown"].append("relevant_personal_evidence_not_found")
    capability = capability_packet or {}
    if capability.get("handled"):
        result["specialist"] = {
            "capability": capability.get("capability"),
            "status": capability.get("status"),
        }
        if capability.get("status") == "ok":
            result["known"].append("specialist_result_available")
            result["unknown"] = [
                item for item in result["unknown"]
                if item != "current_external_facts_until_capability_returns"
            ]
    else:
        result["specialist"] = {"capability": "l_core", "status": "not_required"}
    return result
