"""Project L Phase 2: bounded multi-dimensional confidence assessment."""

from __future__ import annotations

import re


DIMENSIONS = (
    "source",
    "retrieval",
    "memory",
    "interpretation",
    "reasoning",
    "prediction",
)


def _dimension(applicable, level, score, basis, limitations=None):
    return {
        "applicable": bool(applicable),
        "level": level if applicable else "not_applicable",
        "score": score if applicable else None,
        "basis": str(basis),
        "limitations": list(limitations or []),
    }


def _memory_evidence(context: str) -> dict:
    lines = [
        line.strip() for line in str(context or "").splitlines()
        if re.match(r"^\d+(?:\.\d+)?\s*\|\s*(?:memory_|local_)", line.strip(), re.I)
    ]
    user_authored = sum("SOURCE_ROLE=USER" in line.upper() for line in lines)
    assistant_authored = sum("SOURCE_ROLE=ASSISTANT" in line.upper() for line in lines)
    linked = sum("PROVENANCE=LINKED" in line.upper() for line in lines)
    return {
        "records": len(lines),
        "user_authored": user_authored,
        "assistant_authored": assistant_authored,
        "linked": linked,
    }


def assess_confidence_dimensions(
    message: str,
    controller: dict,
    rhee_packet: dict,
    capability_packet: dict,
    mary_packet: dict,
    rike_packet: dict,
) -> dict:
    """Assess six independent confidence dimensions without aggregating them."""
    needs = (controller or {}).get("needs") or {}
    context = str((rhee_packet or {}).get("context") or "")
    evidence = _memory_evidence(context)
    memory_needed = bool(needs.get("memory"))
    external_needed = bool(needs.get("external_evidence"))
    capability = capability_packet or {}

    source_applicable = memory_needed or external_needed or bool(capability.get("handled"))
    if not source_applicable:
        source = _dimension(False, "", None, "No factual source claim was required.")
    elif capability.get("handled") and capability.get("status") != "ok":
        source = _dimension(True, "low", 0.2, "The requested capability did not return a successful evidence result.", ["External evidence is unavailable or incomplete."])
    elif evidence["user_authored"]:
        source = _dimension(True, "high", 0.85, f"{evidence['user_authored']} Doug-authored memory record(s) are present.", ["Source authority does not by itself prove the interpretation."])
    elif evidence["records"] or capability.get("status") == "ok":
        source = _dimension(True, "medium", 0.6, "Evidence is present, but primary-source authority is not established for every claim.", ["Verify consequential claims against primary evidence."])
    else:
        source = _dimension(True, "low", 0.2, "No traceable supporting source was found.", ["Do not fill the evidence gap with inference."])

    if not memory_needed:
        retrieval = _dimension(False, "", None, "Memory retrieval was not requested by the controller.")
        memory = _dimension(False, "", None, "Personal memory was not required for this request.")
    elif not (rhee_packet or {}).get("recall_active"):
        retrieval = _dimension(True, "low", 0.15, "Rhee did not find an active long-term recall packet.", ["Relevant records may be absent, unmatched or unavailable."])
        memory = _dimension(True, "low", 0.15, "No relevant long-term memory was retrieved.", ["L must say that the record was not found rather than guess."])
    else:
        retrieval_score = 0.85 if evidence["records"] >= 3 else 0.65
        retrieval = _dimension(True, "high" if retrieval_score >= 0.8 else "medium", retrieval_score, f"Rhee returned {evidence['records']} traceable long-term record(s).", ["Retrieval confidence measures match quality, not truth of every record."])
        memory_score = 0.88 if evidence["user_authored"] else 0.55
        memory = _dimension(True, "high" if memory_score >= 0.8 else "medium", memory_score, "Memory confidence reflects authorship and provenance of the retrieved records.", ["Conflicting or superseded memories must remain visible."])

    mary = mary_packet or {}
    rike = rike_packet or {}
    interpretation_applicable = bool(mary.get("active") or rike.get("status") == "ok")
    if not interpretation_applicable:
        interpretation = _dimension(False, "", None, "No material interpretation was required.")
    elif mary.get("active") and not mary.get("pattern_threshold_met"):
        interpretation = _dimension(True, "low", 0.3, "Longitudinal interpretation has fewer than two traceable observations.", ["Describe an observation, not a pattern."])
    else:
        conflicts = len(rike.get("conflicts") or [])
        score = 0.62 if conflicts else 0.72
        interpretation = _dimension(True, "medium", score, "Interpretation is supported by the available cognitive packet.", ["Alternative interpretations remain possible."] if conflicts else [])

    reasoning_applicable = rike.get("status") != "not_required"
    if not reasoning_applicable:
        reasoning = _dimension(False, "", None, "Structured reasoning was not required.")
    elif rike.get("status") != "ok":
        reasoning = _dimension(True, "low", 0.2, "RIKE did not produce an accepted structured assessment.", list(rike.get("uncertainties") or []))
    else:
        rike_confidence = rike.get("confidence") or {}
        try:
            score = max(0.0, min(1.0, float(rike_confidence.get("score", 0.25))))
        except (TypeError, ValueError):
            score = 0.25
        level = "high" if score >= 0.8 else "medium" if score >= 0.5 else "low"
        reasoning = _dimension(True, level, score, str(rike_confidence.get("basis") or "RIKE supplied no confidence basis."), list(rike.get("uncertainties") or []))

    prediction_requested = any(signal in str(message or "").lower() for signal in (
        "predict", "prediction", "forecast", "outlook", "likely", "chance", "what will",
        "how will", "expected to",
    ))
    if not prediction_requested:
        prediction = _dimension(False, "", None, "No prediction was requested.")
    else:
        predictive_evidence = bool(capability.get("status") == "ok" or evidence["records"] >= 3)
        prediction = _dimension(
            True,
            "medium" if predictive_evidence else "low",
            0.55 if predictive_evidence else 0.2,
            "Prediction confidence is limited by the supplied point-in-time evidence.",
            ["A plausible forecast is not a known outcome."],
        )

    dimensions = {
        "source": source,
        "retrieval": retrieval,
        "memory": memory,
        "interpretation": interpretation,
        "reasoning": reasoning,
        "prediction": prediction,
    }
    return {
        "engine": "l_multidimensional_uncertainty",
        "version": "1.0",
        "aggregation": "prohibited",
        "dimensions": dimensions,
        "material_limits": [
            f"{name}: {item['basis']}"
            for name, item in dimensions.items()
            if item["applicable"] and item["level"] == "low"
        ],
    }
