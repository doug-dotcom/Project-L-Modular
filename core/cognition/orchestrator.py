"""L's selective cognitive orchestration entrypoint."""

from __future__ import annotations

from agents.quinn.quinn import curate_principles
from core.cognition.anticipation import build_anticipation_packet
from core.cognition.confidence_evidence import build_confidence_evidence_packet
from core.cognition.cue_driven_memory import build_cue_memory_packet
from core.cognition.experience_abstraction import build_experience_abstraction
from core.cognition.learning_engine import build_learning_observation
from core.cognition.memory_contrast import build_memory_contrast_packet
from core.cognition.memory_counterexample import build_memory_counterexample_packet
from core.cognition.memory_relevance import build_memory_relevance_packet
from core.cognition.memory_value import build_memory_value_packet
from core.cognition.multi_agent import build_multi_agent_packet, run_parallel_foundation
from core.cognition.model_independence import (
    OpenAIChatCompletionsAdapter,
    create_model_adapter,
    build_model_independence_packet,
)
from core.cognition.personal_research import build_personal_research_packet
from core.cognition.personal_timeline import build_personal_timeline_packet
from core.cognition.portability import portability_manifest
from core.cognition.relationship_intelligence import build_relationship_packet
from core.cognition.rike import needs_structured_reasoning, reason
from core.cognition.state_aware_response import build_state_aware_response_packet
from core.cognition.what_matters_now import build_what_matters_now_packet
from governance.cognitive_guardrails import assess_cognitive_packet
from core.cognition.controller import finalise_cognition_plan, plan_cognition
from core.cognition.uncertainty import assess_confidence_dimensions


def run_cognitive_core(
    message: str,
    rhee_packet: dict,
    capability_packet: dict | None = None,
    client=None,
    model="gpt-4o-mini",
    cognitive_plan: dict | None = None,
    working_memory_packet: dict | None = None,
    model_adapter=None,
) -> dict:
    resolved_adapter = model_adapter or (
        create_model_adapter(client, model) if client is not None else None
    )
    cognitive_plan = finalise_cognition_plan(
        cognitive_plan or plan_cognition(message),
        rhee_packet,
        capability_packet or {},
    )
    evidence_context = str((rhee_packet or {}).get("context") or "")
    capability_packet = capability_packet or {}
    if capability_packet.get("handled") and capability_packet.get("reply"):
        evidence_context += (
            "\n\nGOVERNED CAPABILITY RESULT\n"
            f"CAPABILITY: {capability_packet.get('capability')}\n"
            f"STATUS: {capability_packet.get('status')}\n"
            f"RESULT: {str(capability_packet.get('reply'))[:12000]}"
        )

    foundation = run_parallel_foundation(
        message,
        evidence_context,
        structured_reasoning_required=bool(cognitive_plan["needs"]["structured_reasoning"]),
    )
    mary = foundation["outputs"]["mary"]
    quinn = foundation["outputs"]["quinn"]
    rike_required = bool(cognitive_plan["needs"]["structured_reasoning"] or mary["active"])

    if rike_required:
        rike = reason(
            message,
            evidence_context=evidence_context,
            mary_packet=mary,
            quinn_packet=quinn,
            client=client,
            model=model,
            model_adapter=resolved_adapter,
        )
    else:
        rike = {
            "engine": "rike",
            "version": "2.0",
            "status": "not_required",
            "activation_reason": "ordinary_conversation",
            "confidence": {"level": "medium", "score": 0.5, "basis": "No structured conclusion requested."},
            "evidence_summary": "Structured reasoning was not required.",
            "uncertainties": ["No structured conclusion was requested."],
            "lenses": [],
            "hypotheses": [],
            "counterfactuals": [],
            "conclusion_change_evidence": [],
            "causal_assessment": {
                "relationship": "none",
                "supported_causal_claim": False,
                "basis": "No causal assessment was required.",
                "limitations": [],
            },
        }

    confidence_dimensions = assess_confidence_dimensions(
        message,
        cognitive_plan,
        rhee_packet,
        capability_packet,
        mary,
        rike,
    )
    confidence_evidence = build_confidence_evidence_packet(
        confidence_dimensions,
        rhee_packet or {},
        capability_packet,
    )
    cue_driven_memory = build_cue_memory_packet(
        message,
        cognitive_plan,
        rhee_packet or {},
        confidence_evidence,
    )
    memory_relevance = build_memory_relevance_packet(
        message,
        cue_driven_memory,
        rhee_packet or {},
        confidence_evidence,
    )
    memory_contrast = build_memory_contrast_packet(
        message,
        cue_driven_memory,
        memory_relevance,
        rhee_packet or {},
    )
    memory_value = build_memory_value_packet(
        message,
        cue_driven_memory,
        memory_relevance,
        memory_contrast,
        rhee_packet or {},
    )
    memory_counterexample = build_memory_counterexample_packet(
        message,
        cue_driven_memory,
        memory_value,
        rhee_packet or {},
    )
    guardrails = assess_cognitive_packet(rike, mary, confidence_dimensions)
    anticipation = build_anticipation_packet(
        message,
        working_memory_packet or {},
        mary,
        rhee_packet or {},
    )
    relationship = build_relationship_packet(message, evidence_context)
    timeline = build_personal_timeline_packet(message, evidence_context)
    state_aware = build_state_aware_response_packet(
        message,
        working_memory_packet or {},
    )
    personal_research = build_personal_research_packet(
        message,
        evidence_context,
        confidence_evidence,
        capability_packet,
    )
    what_matters_now = build_what_matters_now_packet(
        message,
        working_memory_packet or {},
        mary,
        anticipation,
        timeline,
        relationship,
        personal_research,
        confidence_evidence,
    )
    saturation = cue_driven_memory.get("saturation") or {}

    packet = {
        "engine": "project_l_cognitive_core",
        "version": "14.3",
        "controller": cognitive_plan,
        "confidence_dimensions": confidence_dimensions,
        "confidence_evidence": confidence_evidence,
        "cue_driven_memory": cue_driven_memory,
        "associative_saturation": saturation,
        "memory_relevance": memory_relevance,
        "memory_contrast": memory_contrast,
        "memory_value": memory_value,
        "memory_counterexample": memory_counterexample,
        "state_aware_response": state_aware,
        "personal_research": personal_research,
        "what_matters_now": what_matters_now,
        "route": {
            "rhee": "required" if cognitive_plan["needs"]["memory"] else "not_required",
            "mary": "active" if mary["active"] else "not_required",
            "quinn": "advisory" if rike_required else "not_required",
            "rike": "active" if rike_required else "not_required",
            "anticipation": "prepared" if anticipation["active"] else "not_required",
            "relationship_intelligence": "active" if relationship["active"] else "not_required",
            "personal_timeline": "active" if timeline["active"] else "not_required",
            "confidence_evidence": "active",
            "cue_driven_memory": "active" if cue_driven_memory["active"] else "not_required",
            "associative_saturation": (
                "allowed" if saturation.get("allowed") else "suppressed"
                if saturation.get("applies") else "not_required"
            ),
            "memory_relevance": memory_relevance["decision"] if memory_relevance["active"] else "not_required",
            "memory_contrast": memory_contrast["decision"] if memory_contrast["active"] else "not_required",
            "memory_value": memory_value["decision"] if memory_value["active"] else "not_required",
            "memory_counterexample": memory_counterexample["decision"] if memory_counterexample["active"] else "not_required",
            "state_aware_response": "active" if state_aware["active"] else "neutral",
            "personal_research": "active" if personal_research["active"] else "not_required",
            "what_matters_now": "active" if what_matters_now["active"] else "not_required",
        },
        "mary": mary,
        "quinn": quinn if rike_required else {"engine": "quinn", "status": "not_required", "principles": []},
        "rike": rike,
        "anticipation": anticipation,
        "relationship_intelligence": relationship,
        "personal_timeline": timeline,
        "guardrails": guardrails,
        "working_memory": working_memory_packet or {},
        "model_independence": build_model_independence_packet(resolved_adapter),
        "portability": portability_manifest(),
    }
    packet["multi_agent"] = build_multi_agent_packet(
        cognitive_plan,
        rhee_packet or {},
        capability_packet,
        foundation,
        rike,
    )
    abstraction = build_experience_abstraction(message, mary, rike, quinn, guardrails)
    packet["experience_abstraction"] = abstraction
    packet["route"]["experience_abstraction"] = (
        "candidate" if abstraction["active"] else "not_required"
    )
    packet["learning"] = build_learning_observation(packet)
    return packet
