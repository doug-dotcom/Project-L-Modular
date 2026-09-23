"""Deterministic metacognitive planning for Project L.

The controller plans cognition before retrieval or model generation. It does not
answer Doug, infer personal facts, or call tools; it only declares which bounded
systems a request has earned.
"""

from __future__ import annotations

import re

from core.cognition.cue_driven_memory import assess_present_cue
from core.cognition.current_update import self_contained_daily_update
from core.cognition.decision_memory import decision_recall_requested
from core.cognition.personal_research import personal_research_requested
from core.cognition.personal_timeline import timeline_query_requested
from core.cognition.relationship_intelligence import relationship_query_requested
from core.cognition.rike import needs_structured_reasoning
from core.cognition.what_matters_now import what_matters_now_requested


CONTROLLER_VERSION = "1.9"


def _has(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal in text for signal in signals)


def _continuity_signal(text: str) -> bool:
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
        "pick up where we left off", "where we left off", "where were we",
        "what were we doing", "continue from before", "continue from last time",
        "keep building", "keep working on", "back to what we were doing",
        "resume the last", "resume our", "next layer", "another layer",
    ))


def _life_pattern_signal(text: str) -> bool:
    return _has(text, (
        "what have you noticed", "what are you noticing", "what do you notice",
        "join the dots", "connect the dots", "recurring theme", "recurring themes",
        "common thread", "common threads", "what tends to happen", "keeps happening",
        "keeps coming up", "what keeps coming up", "across my life", "across my health",
        "across recovery", "across my recovery", "across my projects", "across family",
        "across my family", "life pattern", "life patterns", "bigger picture",
        "how things connect", "how these things connect", "connections between",
        "themes in my life", "themes lately",
    ))


def plan_cognition(message: str) -> dict:
    raw_text = str(message or "").strip()
    text = " ".join(raw_text.lower().split())
    current_update = self_contained_daily_update(raw_text)

    continuity_signal = _continuity_signal(text)
    life_pattern_signal = _life_pattern_signal(text)
    decision_signal = decision_recall_requested(text)
    relationship_signal = relationship_query_requested(raw_text)
    timeline_signal = timeline_query_requested(raw_text)
    research_signal = personal_research_requested(raw_text)
    what_matters_signal = what_matters_now_requested(raw_text)
    cue_assessment = (
        {"should_retrieve": False, "reason": "self_contained_daily_update",
         "evidence_basis": "current_user_message"}
        if current_update else assess_present_cue(raw_text)
    )
    cue_signal = bool(cue_assessment.get("should_retrieve"))

    explicit_recall_signal = not current_update and (
        continuity_signal or life_pattern_signal or decision_signal or relationship_signal
        or timeline_signal or research_signal or what_matters_signal or _has(text, (
            "remember", "recall", "deep recall", "what do you know", "tell me about my",
            "my recovery", "my family", "my history", "my journey", "my project",
            "we discussed", "we decided", "we built", "earlier", "last time", "again",
            "still", "continue", "update it", "same as before", "our plan", "our project",
        ))
    )
    associative_only = cue_signal and not explicit_recall_signal
    recall_signal = explicit_recall_signal or cue_signal

    longitudinal_signal = not current_update and (life_pattern_signal or timeline_signal or what_matters_signal or _has(text, (
        "pattern", "over time", "timeline", "changed", "progress", "last six months",
        "last 6 months", "weekly report", "report for pauline", "journey",
    )))
    current_evidence_signal = research_signal or _has(text, (
        "latest", "current", "today's", "today’s", "news", "research", "look up",
        "search", "verify online", "weather", "market", "price", "schedule",
        "email", "gmail", "calendar", "tasks", "transactions", "bank statement",
    ))
    action_signal = bool(re.search(
        r"\b(?:send|delete|create|schedule|book|upload|download|add|remove|cancel)\b",
        text,
    ))
    structured = (not current_update and needs_structured_reasoning(text)) or longitudinal_signal or research_signal or what_matters_signal
    high_stakes = _has(text, (
        "medical", "diagnosis", "legal", "insurance claim", "tpd", "financial advice",
        "suicide", "self-harm", "overdose", "emergency",
    ))

    if action_signal:
        problem_type = "action"
    elif what_matters_signal:
        problem_type = "what_matters_now"
    elif life_pattern_signal:
        problem_type = "life_pattern"
    elif decision_signal:
        problem_type = "decision_recall"
    elif timeline_signal:
        problem_type = "personal_timeline"
    elif relationship_signal:
        problem_type = "relationship_intelligence"
    elif research_signal:
        problem_type = "personal_research"
    elif longitudinal_signal:
        problem_type = "longitudinal"
    elif explicit_recall_signal:
        problem_type = "personal_recall"
    elif current_evidence_signal:
        problem_type = "external_evidence"
    elif structured:
        problem_type = "analysis"
    else:
        # Pure cue-driven retrieval should still feel like ordinary conversation.
        problem_type = "conversation"

    substantial = problem_type != "conversation" or len(text.split()) >= 18
    memory_required = recall_signal or longitudinal_signal
    external_evidence_required = current_evidence_signal or high_stakes
    difficulty_score = sum((
        substantial, structured, longitudinal_signal, high_stakes, action_signal,
        life_pattern_signal, decision_signal, relationship_signal, timeline_signal,
        research_signal, what_matters_signal,
    ))
    difficulty = "high" if difficulty_score >= 3 else "medium" if difficulty_score >= 1 else "low"

    known = []
    unknown = []
    if current_update:
        known.append("daily_update_supplied_in_current_message")
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
    if timeline_signal:
        unknown.append("dated_timeline_evidence_until_retrieved")
    if research_signal:
        unknown.append("research_brief_evidence_until_retrieved")
    if what_matters_signal:
        unknown.append("current_priority_evidence_until_retrieved")
    if associative_only:
        unknown.append("associative_memory_relevance_until_retrieved")
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
        "associative_cue": cue_assessment,
        "needs": {
            "memory": memory_required,
            "external_evidence": external_evidence_required,
            "structured_reasoning": structured or high_stakes,
            "longitudinal_reasoning": longitudinal_signal,
            "continuity": continuity_signal,
            "life_pattern": life_pattern_signal,
            "decision_memory": decision_signal,
            "relationship_intelligence": relationship_signal,
            "personal_timeline": timeline_signal,
            "personal_research": research_signal,
            "what_matters_now": what_matters_signal,
            "cue_driven_memory": associative_only,
            "specialist": external_evidence_required or action_signal,
        },
        "signals": {
            "self_contained_daily_update": current_update,
            "recall": recall_signal,
            "explicit_recall": explicit_recall_signal,
            "cue_driven_memory": associative_only,
            "continuity": continuity_signal,
            "life_pattern": life_pattern_signal,
            "decision_memory": decision_signal,
            "relationship_intelligence": relationship_signal,
            "personal_timeline": timeline_signal,
            "personal_research": research_signal,
            "what_matters_now": what_matters_signal,
            "longitudinal": longitudinal_signal,
            "current_evidence": current_evidence_signal,
            "action": action_signal,
            "high_stakes": high_stakes,
        },
    }


def finalise_cognition_plan(plan: dict, rhee_packet: dict, capability_packet: dict) -> dict:
    result = {**(plan or {})}
    result["known"] = list(result.get("known") or [])
    result["unknown"] = list(result.get("unknown") or [])
    if result.get("needs", {}).get("memory"):
        marker = "relevant_personal_evidence_until_retrieved"
        if (rhee_packet or {}).get("recall_active"):
            result["known"].append("personal_evidence_retrieved")
            result["unknown"] = [item for item in result["unknown"] if item != marker]
            mappings = (
                ("continuity", "prior_thread_evidence_retrieved", "prior_thread_until_retrieved"),
                ("life_pattern", "pattern_candidate_evidence_retrieved", "cross_domain_pattern_evidence_until_retrieved"),
                ("decision_memory", "decision_evidence_retrieved", "decision_rationale_until_retrieved"),
                ("relationship_intelligence", "relationship_evidence_retrieved", "relationship_evidence_until_retrieved"),
                ("personal_timeline", "dated_timeline_evidence_retrieved", "dated_timeline_evidence_until_retrieved"),
                ("personal_research", "research_brief_evidence_retrieved", "research_brief_evidence_until_retrieved"),
                ("what_matters_now", "current_priority_evidence_retrieved", "current_priority_evidence_until_retrieved"),
                ("cue_driven_memory", "associative_memory_evidence_retrieved", "associative_memory_relevance_until_retrieved"),
            )
            for need, known_value, unknown_value in mappings:
                if result.get("needs", {}).get(need):
                    result["known"].append(known_value)
                    result["unknown"] = [item for item in result["unknown"] if item != unknown_value]
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
