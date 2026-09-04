"""L's selective cognitive orchestration entrypoint."""

from __future__ import annotations

from agents.quinn.quinn import curate_principles
from core.cognition.longitudinal import build_longitudinal_packet
from core.cognition.learning_engine import build_learning_observation
from core.cognition.rike import needs_structured_reasoning, reason
from governance.cognitive_guardrails import assess_cognitive_packet


def run_cognitive_core(
    message: str,
    rhee_packet: dict,
    capability_packet: dict | None = None,
    client=None,
    model="gpt-4o-mini",
) -> dict:
    evidence_context = str((rhee_packet or {}).get("context") or "")
    capability_packet = capability_packet or {}
    if capability_packet.get("handled") and capability_packet.get("reply"):
        evidence_context += (
            "\n\nGOVERNED CAPABILITY RESULT\n"
            f"CAPABILITY: {capability_packet.get('capability')}\n"
            f"STATUS: {capability_packet.get('status')}\n"
            f"RESULT: {str(capability_packet.get('reply'))[:12000]}"
        )
    mary = build_longitudinal_packet(message, evidence_context)
    quinn = curate_principles(message)
    rike_required = needs_structured_reasoning(message) or mary["active"]

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
            "version": "1.0",
            "status": "not_required",
            "activation_reason": "ordinary_conversation",
            "confidence": {"level": "medium", "score": 0.5, "basis": "No structured conclusion requested."},
            "evidence_summary": "Structured reasoning was not required.",
            "uncertainties": ["No structured conclusion was requested."],
            "lenses": [],
        }

    guardrails = assess_cognitive_packet(rike, mary)
    packet = {
        "engine": "project_l_cognitive_core",
        "version": "1.0",
        "route": {
            "rhee": "required",
            "mary": "active" if mary["active"] else "not_required",
            "quinn": "advisory" if rike_required else "not_required",
            "rike": "active" if rike_required else "not_required",
        },
        "mary": mary,
        "quinn": quinn if rike_required else {"engine": "quinn", "status": "not_required", "principles": []},
        "rike": rike,
        "guardrails": guardrails,
    }
    packet["learning"] = build_learning_observation(packet)
    return packet
