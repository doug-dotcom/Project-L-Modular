"""L's selective cognitive orchestration entrypoint."""

from __future__ import annotations

from agents.quinn.quinn import curate_principles
from core.cognition.experience_abstraction import build_experience_abstraction
from core.cognition.learning_engine import build_learning_observation
from core.cognition.multi_agent import build_multi_agent_packet, run_parallel_foundation
from core.cognition.rike import needs_structured_reasoning, reason
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
) -> dict:
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
    guardrails = assess_cognitive_packet(rike, mary, confidence_dimensions)
    packet = {
        "engine": "project_l_cognitive_core",
        "version": "11.0",
        "controller": cognitive_plan,
        "confidence_dimensions": confidence_dimensions,
        "route": {
            "rhee": "required" if cognitive_plan["needs"]["memory"] else "not_required",
            "mary": "active" if mary["active"] else "not_required",
            "quinn": "advisory" if rike_required else "not_required",
            "rike": "active" if rike_required else "not_required",
        },
        "mary": mary,
        "quinn": quinn if rike_required else {"engine": "quinn", "status": "not_required", "principles": []},
        "rike": rike,
        "guardrails": guardrails,
        "working_memory": working_memory_packet or {},
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
