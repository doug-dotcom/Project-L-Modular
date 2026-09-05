"""RIKE: Project L's model-agnostic structured reasoning engine."""

from __future__ import annotations

import json
import re

from core.cognition.brains_trust import select_lenses
from core.cognition.model_independence import (
    OpenAIChatCompletionsAdapter,
    create_model_adapter,
    build_model_request,
    invoke_model,
)


REASONING_SIGNALS = (
    "analyse", "analyze", "assess", "best option", "compare", "conflict",
    "contradiction", "decide", "diagnose", "evaluate", "explain why",
    "how should", "make sense of", "pros and cons", "reason", "recommend",
    "risk", "should i", "trade-off", "what caused", "why did", "why is",
    "what should", "which is better", "which one", "swot", "self audit",
    "self-audit", "audit yourself", "your capabilities",
)

HYPOTHESIS_STATUSES = {"supported", "plausible", "weakened", "insufficient"}
CAUSAL_RELATIONSHIPS = {
    "none",
    "correlation",
    "association",
    "plausible_mechanism",
    "supported_causal_claim",
}


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
        "version": "2.0",
        "status": "degraded",
        "activation_reason": reason,
        "question": question,
        "lenses": [lens["name"] for lens in lenses],
        "evidence_summary": "Retrieved context is available for L to assess." if evidence_present else "No supporting evidence packet was available.",
        "assumptions": [],
        "hypotheses": [],
        "conflicts": [],
        "alternative_explanations": [],
        "conclusion_change_evidence": [],
        "counterfactuals": [],
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
        "causal_assessment": {
            "relationship": "none",
            "supported_causal_claim": False,
            "basis": "No accepted structured reasoning established a causal relationship.",
            "limitations": ["RIKE model reasoning was unavailable."],
        },
    }


def _strings(value, limit: int = 8, length: int = 800) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item)[:length] for item in value[:limit] if str(item).strip()]


def _normalise_hypotheses(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    hypotheses = []
    for index, raw in enumerate(value[:6], start=1):
        item = raw if isinstance(raw, dict) else {"claim": raw}
        status = str(item.get("status") or "insufficient").lower()
        if status not in HYPOTHESIS_STATUSES:
            status = "insufficient"
        supporting = item.get("supporting_evidence", item.get("support", []))
        contradictory = item.get("contradictory_evidence", item.get("counterevidence", []))
        if not isinstance(supporting, list):
            supporting = [supporting] if supporting else []
        if not isinstance(contradictory, list):
            contradictory = [contradictory] if contradictory else []
        hypotheses.append({
            "id": str(item.get("id") or f"H{index}")[:40],
            "claim": str(item.get("claim") or "")[:1000],
            "supporting_evidence": _strings(supporting),
            "contradictory_evidence": _strings(contradictory),
            "assumptions": _strings(item.get("assumptions")),
            "alternative_explanations": _strings(item.get("alternative_explanations")),
            "status": status,
        })
    return hypotheses


def _normalise_counterfactuals(value) -> list[dict]:
    if not isinstance(value, list):
        return []
    counterfactuals = []
    for raw in value[:6]:
        item = raw if isinstance(raw, dict) else {"condition": raw}
        counterfactuals.append({
            "condition": str(item.get("condition") or "")[:1000],
            "expected_result": str(item.get("expected_result") or "")[:1000],
            "implication": str(item.get("implication") or "")[:1000],
            "limitations": _strings(item.get("limitations"), limit=4),
        })
    return counterfactuals


def _normalise_packet(
    data: dict,
    question: str,
    lenses: list[dict],
    evidence_context: str = "",
) -> dict:
    confidence = data.get("confidence") if isinstance(data.get("confidence"), dict) else {}
    level = str(confidence.get("level") or "low").lower()
    if level not in {"low", "medium", "high"}:
        level = "low"
    try:
        score = max(0.0, min(1.0, float(confidence.get("score", 0.25))))
    except (TypeError, ValueError):
        score = 0.25

    causal = data.get("causal_assessment") if isinstance(data.get("causal_assessment"), dict) else {}
    relationship = str(causal.get("relationship") or "none").lower()
    if relationship not in CAUSAL_RELATIONSHIPS:
        relationship = "none"
    direct = data.get("direct_causal_evidence") if isinstance(data.get("direct_causal_evidence"), dict) else {}
    evidence_quotes = _strings(direct.get("evidence_quotes"), limit=4, length=500)
    evidence_text = str(evidence_context or "").casefold()
    quotes_verified = bool(evidence_quotes) and all(
        quote.casefold() in evidence_text for quote in evidence_quotes
    )
    causal_supported = bool(
        relationship == "supported_causal_claim"
        and causal.get("supported_causal_claim") is True
        and direct.get("established") is True
        and quotes_verified
    )

    packet = {
        "engine": "rike",
        "version": "2.0",
        "status": "ok",
        "activation_reason": str(data.get("activation_reason") or "complex_request")[:300],
        "question": question,
        "lenses": [lens["name"] for lens in lenses],
        "evidence_summary": str(data.get("evidence_summary") or "")[:1800],
        "assumptions": list(data.get("assumptions") or [])[:8],
        "hypotheses": _normalise_hypotheses(data.get("hypotheses")),
        "conflicts": list(data.get("conflicts") or [])[:8],
        "alternative_explanations": _strings(data.get("alternative_explanations")),
        "conclusion_change_evidence": _strings(data.get("conclusion_change_evidence")),
        "counterfactuals": _normalise_counterfactuals(data.get("counterfactuals")),
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
            "established": causal_supported,
            "basis": str(direct.get("basis") or "")[:800],
            "evidence_quotes": evidence_quotes,
            "verified_against_context": quotes_verified,
        },
        "causal_assessment": {
            "relationship": relationship,
            "supported_causal_claim": causal_supported,
            "basis": str(causal.get("basis") or "")[:800],
            "limitations": _strings(causal.get("limitations"), limit=6),
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
    model_adapter=None,
) -> dict:
    """Return an inspectable reasoning packet, never private chain-of-thought."""
    clean_question = str(question or "").strip()
    lenses = select_lenses(clean_question)
    if not clean_question:
        return _fallback_packet(clean_question, evidence_context, lenses, "empty_question")
    adapter = model_adapter or (
        create_model_adapter(client, model) if client is not None else None
    )
    if adapter is None or not getattr(adapter, "available", False):
        return _fallback_packet(clean_question, evidence_context, lenses, "model_unavailable")

    payload = {
        "question": clean_question,
        "evidence_context": str(evidence_context or "")[:14000],
        "brains_trust_lenses": lenses,
        "mary_longitudinal_packet": mary_packet or {},
        "quinn_principles": (quinn_packet or {}).get("principles", []),
    }
    system = """
You are RIKE 2, Project L's hypothesis and counterfactual reasoning engine. You do not
speak to Doug. Analyse only the supplied question, evidence, principles and constraints.
Distinguish retrieved evidence from inference, preserve contradictions, and never invent
a source or memory.

Treat Mary's lifecycle packet as bounded longitudinal evidence. Current identity and
current evidence outrank historical, weakening or superseded patterns. Never describe
historical Doug as Doug's current identity without current corroboration.

Generate at least two genuinely competing hypotheses when status is ok. For each return:
id, claim, supporting_evidence[], contradictory_evidence[], assumptions[],
alternative_explanations[], status (supported|plausible|weakened|insufficient).
An empty evidence list means none was found; never fill it with invented support.

Expose global assumptions and alternative_explanations. Return
conclusion_change_evidence[] stating what new evidence would materially change the
conclusion. Return counterfactuals[] with condition, expected_result, implication and
limitations[]. Counterfactuals are tests of reasoning, not facts about what occurred.

Classify the strongest justified relationship as exactly one of: none, correlation,
association, plausible_mechanism, supported_causal_claim. Correlation and association
are not causation. A plausible mechanism is not a supported causal claim. Return
causal_assessment {relationship, supported_causal_claim, basis, limitations[]} and
direct_causal_evidence {established, basis, evidence_quotes[]}. Both causal booleans may
be true only when evidence_quotes contains the exact supplied evidence text that explicitly
attributes the event or outcome to that cause. Similar themes, later reflections,
chronology and counterfactual plausibility are insufficient.

Return JSON only with activation_reason, evidence_summary, assumptions, hypotheses,
conflicts, alternative_explanations, conclusion_change_evidence, counterfactuals,
conclusion, confidence {level: low|medium|high, score: 0..1, basis}, uncertainties,
recommended_action, rationale_summary, direct_causal_evidence and causal_assessment.
rationale_summary is a concise inspectable justification, never hidden chain-of-thought
or token-by-token deliberation.
""".strip()

    try:
        request = build_model_request(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            purpose="rike_structured_reasoning",
            temperature=0.15,
            response_format={"type": "json_object"},
        )
        result = invoke_model(adapter, request)
        data = json.loads(result["content"] or "{}")
        if not isinstance(data, dict):
            raise ValueError("RIKE response was not an object")
        packet = _normalise_packet(data, clean_question, lenses, evidence_context)
        packet["model_receipt"] = result.get("receipt", {})
        return packet
    except Exception as exc:
        return _fallback_packet(
            clean_question,
            evidence_context,
            lenses,
            f"reasoning_error:{type(exc).__name__}",
        )
