"""Project L Layer 7: claim-level confidence and evidence policy.

This layer converts L's existing independent confidence dimensions and retrieved
receipts into a simple publication policy. It does not create evidence or an
aggregate confidence score. Its job is to stop fact, inference, prediction and
unknown states from bleeding into one another while keeping L's language natural.
"""

from __future__ import annotations


CONFIDENCE_EVIDENCE_VERSION = "1.0"


def _level(dimensions: dict, name: str) -> str:
    item = ((dimensions or {}).get("dimensions") or {}).get(name) or {}
    return str(item.get("level") or "not_applicable")


def _applicable(dimensions: dict, name: str) -> bool:
    item = ((dimensions or {}).get("dimensions") or {}).get(name) or {}
    return bool(item.get("applicable"))


def build_confidence_evidence_packet(
    confidence_dimensions: dict | None,
    rhee_packet: dict | None,
    capability_packet: dict | None,
) -> dict:
    """Build a non-aggregated claim policy for L's final synthesis."""
    dims = confidence_dimensions or {}
    rhee = rhee_packet or {}
    capability = capability_packet or {}
    evidence = list(rhee.get("evidence") or [])

    traceable_sources = [
        str(item.get("source")) for item in evidence
        if isinstance(item, dict) and item.get("source")
    ]
    source_level = _level(dims, "source")
    retrieval_level = _level(dims, "retrieval")
    memory_level = _level(dims, "memory")
    interpretation_level = _level(dims, "interpretation")
    reasoning_level = _level(dims, "reasoning")
    prediction_level = _level(dims, "prediction")

    personal_fact_allowed = bool(
        traceable_sources
        and source_level not in {"low", "not_applicable"}
        and retrieval_level not in {"low"}
        and memory_level not in {"low"}
    )
    external_fact_allowed = bool(
        capability.get("handled")
        and capability.get("status") == "ok"
        and source_level not in {"low", "not_applicable"}
    )
    supported_inference_allowed = bool(
        traceable_sources
        and interpretation_level in {"medium", "high"}
        and (not _applicable(dims, "reasoning") or reasoning_level in {"medium", "high"})
    )
    prediction_allowed = bool(
        _applicable(dims, "prediction")
        and prediction_level in {"medium", "high"}
    )

    missing_evidence = bool(
        (_applicable(dims, "retrieval") and retrieval_level == "low")
        or (_applicable(dims, "memory") and memory_level == "low")
        or (_applicable(dims, "source") and source_level == "low")
    )

    permitted = ["conversation"]
    if personal_fact_allowed or external_fact_allowed:
        permitted.append("fact")
    if supported_inference_allowed:
        permitted.append("supported_inference")
    elif traceable_sources:
        permitted.append("tentative_inference")
    if prediction_allowed:
        permitted.append("prediction")
    if missing_evidence or not traceable_sources:
        permitted.append("unknown")

    return {
        "engine": "confidence_evidence_layer",
        "version": CONFIDENCE_EVIDENCE_VERSION,
        "aggregation": "prohibited",
        "traceable_source_count": len(traceable_sources),
        "traceable_sources": traceable_sources[:12],
        "claim_permissions": {
            "personal_fact": personal_fact_allowed,
            "external_fact": external_fact_allowed,
            "supported_inference": supported_inference_allowed,
            "prediction": prediction_allowed,
            "unknown": missing_evidence or not traceable_sources,
        },
        "permitted_claim_kinds": permitted,
        "instruction": (
            "Speak naturally. Present a personal fact only when traceable evidence and the relevant "
            "source/retrieval/memory dimensions permit it. Present an interpretation only as an "
            "interpretation; use ordinary hedging such as 'it looks like', 'I think' or 'one plausible "
            "reading is' when material. Predictions must remain forecasts, never facts. If evidence is "
            "missing, say the specific thing you cannot establish rather than using generic boilerplate. "
            "Do not announce confidence scores, internal dimensions, claim classes or evidence machinery "
            "unless Doug explicitly asks for them. Never average independent confidence dimensions."
        ),
        "governance": {
            "fact_requires_traceable_support": True,
            "inference_must_not_be_presented_as_fact": True,
            "prediction_must_not_be_presented_as_fact": True,
            "missing_evidence_must_remain_unknown": True,
            "natural_language_over_system_labels": True,
            "confidence_score_aggregation": False,
        },
    }


__all__ = ["CONFIDENCE_EVIDENCE_VERSION", "build_confidence_evidence_packet"]
