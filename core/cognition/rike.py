"""RIKE: Project L's model-agnostic structured reasoning engine."""

from __future__ import annotations

import json
import re

from core.cognition.brains_trust import select_lenses


REASONING_SIGNALS = (
    "analyse", "analyze", "assess", "best option", "compare", "conflict",
    "contradiction", "decide", "diagnose", "evaluate", "explain why",
    "how should", "make sense of", "pros and cons", "reason", "recommend",
    "risk", "should i", "trade-off", "what caused", "why did", "why is",
    "what should", "which is better", "which one", "swot", "self audit",
    "self-audit", "audit yourself", "your capabilities",
)


def needs_structured_reasoning(message: str) -> bool:
    text = str(message or "").strip().lower()
    if not text:
        return False
    hits = sum(signal in text for signal in REASONING_SIGNALS)
    words = len(re.findall(r"[a-z0-9']+", text))
    return hits >= 1 or words >= 45


def _fallback_packet(question: str, evidence_context: str, lenses: list[dict], reason: str) -> dict:
    evidence_present = (
        "LONG TERM RECALL ACTIVE: True" in evidence_context
        or "GOVERNED CAPABILITY RESULT" in evidence_context
    )
    return {
        "engine": "rike",
        "version": "1.0",
        "status": "degraded",
        "activation_reason": reason,
        "question": question,
        "lenses": [lens["name"] for lens in lenses],
        "evidence_summary": "Retrieved context is available for L to assess." if evidence_present else "No supporting evidence packet was available.",
        "assumptions": [],
        "hypotheses": [],
        "conflicts": [],
        "conclusion": "",
        "confidence": {
            "level": "medium" if evidence_present else "low",
            "score": 0.55 if evidence_present else 0.25,
            "basis": "RIKE model reasoning unavailable; confidence is limited to packet availability.",
        },
        "uncertainties": ["A structured model assessment was not available."],
        "recommended_action": "Use the retrieved evidence cautiously and state what remains unknown.",
        "rationale_summary": "No model-generated rationale was accepted.",
        "direct_causal_evidence": {
            "established": False,
            "basis": "No accepted structured reasoning established a direct cause.",
        },
    }


def _normalise_packet(data: dict, question: str, lenses: list[dict]) -> dict:
    confidence = data.get("confidence") if isinstance(data.get("confidence"), dict) else {}
    level = str(confidence.get("level") or "low").lower()
    if level not in {"low", "medium", "high"}:
        level = "low"
    try:
        score = max(0.0, min(1.0, float(confidence.get("score", 0.25))))
    except (TypeError, ValueError):
        score = 0.25

    packet = {
        "engine": "rike",
        "version": "1.0",
        "status": "ok",
        "activation_reason": str(data.get("activation_reason") or "complex_request")[:300],
        "question": question,
        "lenses": [lens["name"] for lens in lenses],
        "evidence_summary": str(data.get("evidence_summary") or "")[:1800],
        "assumptions": list(data.get("assumptions") or [])[:8],
        "hypotheses": list(data.get("hypotheses") or [])[:6],
        "conflicts": list(data.get("conflicts") or [])[:8],
        "conclusion": str(data.get("conclusion") or "")[:1500],
        "confidence": {
            "level": level,
            "score": score,
            "basis": str(confidence.get("basis") or "")[:800],
        },
        "uncertainties": list(data.get("uncertainties") or [])[:8],
        "recommended_action": str(data.get("recommended_action") or "")[:1200],
        "rationale_summary": str(data.get("rationale_summary") or "")[:1800],
        "direct_causal_evidence": {
            "established": bool(
                (data.get("direct_causal_evidence") or {}).get("established")
            ) if isinstance(data.get("direct_causal_evidence"), dict) else False,
            "basis": str(
                (data.get("direct_causal_evidence") or {}).get("basis") or ""
            )[:800] if isinstance(data.get("direct_causal_evidence"), dict) else "",
        },
    }
    if not packet["uncertainties"]:
        packet["uncertainties"] = ["No uncertainty analysis was supplied; treat confidence as low."]
        packet["confidence"]["level"] = "low"
        packet["confidence"]["score"] = min(packet["confidence"]["score"], 0.35)
    return packet


def reason(
    question: str,
    evidence_context: str = "",
    mary_packet: dict | None = None,
    quinn_packet: dict | None = None,
    client=None,
    model: str = "gpt-4o-mini",
) -> dict:
    """Return an inspectable reasoning packet, never private chain-of-thought."""
    clean_question = str(question or "").strip()
    lenses = select_lenses(clean_question)
    if not clean_question:
        return _fallback_packet(clean_question, evidence_context, lenses, "empty_question")
    if client is None:
        return _fallback_packet(clean_question, evidence_context, lenses, "model_unavailable")

    payload = {
        "question": clean_question,
        "evidence_context": str(evidence_context or "")[:14000],
        "brains_trust_lenses": lenses,
        "mary_longitudinal_packet": mary_packet or {},
        "quinn_principles": (quinn_packet or {}).get("principles", []),
    }
    system = """
You are RIKE, Project L's structured reasoning engine. You do not speak to Doug.
Analyse only the supplied question, evidence, principles and constraints. Distinguish
retrieved evidence from inference. Preserve contradictions. Do not claim that one
event proves a pattern. Never invent a source or memory. For a question asking why
a past personal event happened, state a cause only when the supplied evidence directly
attributes that cause; later insights and surrounding circumstances are context, not
causal proof. Return JSON only with:
activation_reason, evidence_summary, assumptions, hypotheses, conflicts, conclusion,
confidence {level: low|medium|high, score: 0..1, basis}, uncertainties,
recommended_action, rationale_summary. Hypotheses must be concise claim/support/
counterevidence objects. rationale_summary is a short inspectable justification, not
hidden chain-of-thought or token-by-token deliberation.
Also return direct_causal_evidence {established: boolean, basis: string}. Set
established true only when the supplied evidence explicitly attributes the event to
that cause. Similar themes, later reflections and chronological proximity are false.
""".strip()

    try:
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.15,
        )
        data = json.loads(response.choices[0].message.content or "{}")
        if not isinstance(data, dict):
            raise ValueError("RIKE response was not an object")
        return _normalise_packet(data, clean_question, lenses)
    except Exception as exc:
        return _fallback_packet(
            clean_question,
            evidence_context,
            lenses,
            f"reasoning_error:{type(exc).__name__}",
        )
