"""Layer 98: adaptive generation context budgets for Project L.

The full cognitive packet is retained for runtime/audit purposes. This module builds
only the cognitive subset sent to the response model, removing inactive and
separately-rendered sections first. It never edits Rhee evidence, working memory,
the controller plan, or the stored cognitive packet.
"""

from __future__ import annotations

import json


CONTEXT_BUDGET_VERSION = "1.0"
MODE_BUDGETS = {
    "lean": 12_000,
    "standard": 24_000,
    "expanded": 64_000,
}

# These are already rendered as their own prompt sections (or are audit-only), so
# duplicating them inside COGNITIVE PACKET adds context pressure without signal.
SEPARATELY_RENDERED = {
    "controller",
    "working_memory",
    "model_independence",
    "portability",
    "context_budget",
}

BASE_KEYS = (
    "engine",
    "version",
    "runtime",
    "route",
    "guardrails",
)

ROUTE_TO_PACKET = {
    "mary": "mary",
    "quinn": "quinn",
    "rike": "rike",
    "anticipation": "anticipation",
    "relationship_intelligence": "relationship_intelligence",
    "personal_timeline": "personal_timeline",
    "confidence_evidence": "confidence_evidence",
    "cue_driven_memory": "cue_driven_memory",
    "associative_saturation": "associative_saturation",
    "memory_relevance": "memory_relevance",
    "memory_contrast": "memory_contrast",
    "memory_value": "memory_value",
    "memory_counterexample": "memory_counterexample",
    "memory_applicability": "memory_applicability",
    "memory_temporal_drift": "memory_temporal_drift",
    "memory_privacy": "memory_privacy",
    "memory_identity": "memory_identity",
    "memory_emotional_salience": "memory_emotional_salience",
    "memory_causal_attribution": "memory_causal_attribution",
    "state_aware_response": "state_aware_response",
    "personal_research": "personal_research",
    "what_matters_now": "what_matters_now",
    "experience_abstraction": "experience_abstraction",
}

INACTIVE_ROUTE_STATES = {
    "",
    "not_required",
    "inactive",
    "neutral",
    "suppressed",
    "skipped",
}

# Lowest-value sections are removed first only if the selected packet still exceeds
# its target. Active reasoning/evidence sections are protected.
DROP_PRIORITY = (
    "learning",
    "experience_abstraction",
    "multi_agent",
    "state_aware_response",
    "anticipation",
    "associative_saturation",
    "memory_value",
    "memory_emotional_salience",
    "memory_causal_attribution",
    "memory_contrast",
    "memory_counterexample",
    "memory_applicability",
    "memory_temporal_drift",
    "memory_relevance",
)


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _mode(controller: dict, evidence_required: bool) -> str:
    controller = controller or {}
    needs = controller.get("needs") or {}
    difficulty = str(controller.get("difficulty") or "low").lower()
    if (
        evidence_required
        or difficulty == "high"
        or needs.get("structured_reasoning")
        or needs.get("longitudinal_reasoning")
    ):
        return "expanded"
    if (
        difficulty == "medium"
        or needs.get("memory")
        or needs.get("current_evidence")
        or needs.get("specialist")
        or needs.get("action")
    ):
        return "standard"
    return "lean"


def _active_route_keys(packet: dict) -> set[str]:
    active: set[str] = set()
    route = packet.get("route") or {}
    for route_name, state in route.items():
        packet_key = ROUTE_TO_PACKET.get(route_name)
        if not packet_key or packet_key not in packet:
            continue
        if str(state or "").lower() not in INACTIVE_ROUTE_STATES:
            active.add(packet_key)
    return active


def _supplemental_active(packet: dict) -> set[str]:
    active: set[str] = set()
    multi = packet.get("multi_agent")
    if isinstance(multi, dict) and str(multi.get("status") or "").lower() not in {
        "", "not_required", "inactive", "skipped"
    }:
        active.add("multi_agent")
    abstraction = packet.get("experience_abstraction")
    if isinstance(abstraction, dict) and abstraction.get("active") is True:
        active.add("experience_abstraction")
    learning = packet.get("learning")
    if isinstance(learning, dict) and str(learning.get("status") or "").lower() not in {
        "", "not_required", "inactive", "skipped"
    }:
        active.add("learning")
    return active


def build_generation_cognitive_context(
    cognitive_packet: dict,
    *,
    evidence_required: bool = False,
) -> dict:
    """Return a bounded model-facing cognitive packet plus privacy-safe receipt."""
    packet = dict(cognitive_packet or {})
    controller = packet.get("controller") or {}
    mode = _mode(controller, evidence_required)
    budget = MODE_BUDGETS[mode]

    full_chars = len(_json(packet))
    active_keys = _active_route_keys(packet) | _supplemental_active(packet)

    selected: dict = {}
    for key in BASE_KEYS:
        if key in packet:
            selected[key] = packet[key]

    # Confidence dimensions are compact and directly govern calibrated wording.
    if "confidence_dimensions" in packet:
        selected["confidence_dimensions"] = packet["confidence_dimensions"]

    # Include every route-activated section. Expanded mode also retains the
    # high-value reasoning trio when present, even if their status is advisory.
    for key in sorted(active_keys):
        selected[key] = packet[key]
    if mode == "expanded":
        for key in ("rike", "mary", "quinn", "confidence_evidence"):
            if key in packet:
                selected[key] = packet[key]

    protected = set(BASE_KEYS) | {"confidence_dimensions"}
    protected |= active_keys
    if mode == "expanded":
        protected |= {"rike", "mary", "quinn", "confidence_evidence"}

    rendered = _json(selected)
    dropped_for_budget: list[str] = []
    if len(rendered) > budget:
        for key in DROP_PRIORITY:
            if len(rendered) <= budget:
                break
            if key in selected and key not in protected:
                selected.pop(key, None)
                dropped_for_budget.append(key)
                rendered = _json(selected)

    included = sorted(selected)
    omitted = sorted(
        key for key in packet
        if key not in selected and key not in SEPARATELY_RENDERED
    )
    separately_rendered = sorted(key for key in packet if key in SEPARATELY_RENDERED)

    rendered_chars = len(rendered)
    if rendered_chars <= budget:
        pressure = "within_budget"
    else:
        pressure = "required_context_exceeds_budget"

    receipt = {
        "version": CONTEXT_BUDGET_VERSION,
        "mode": mode,
        "budget_chars": budget,
        "full_packet_chars": full_chars,
        "rendered_chars": rendered_chars,
        "reduction_chars": max(0, full_chars - rendered_chars),
        "reduction_ratio": round(
            (max(0, full_chars - rendered_chars) / full_chars), 4
        ) if full_chars else 0.0,
        "included_sections": included,
        "omitted_sections": omitted,
        "separately_rendered_sections": separately_rendered,
        "dropped_for_budget": dropped_for_budget,
        "pressure": pressure,
        "required_context_preserved": True,
        "rhee_evidence_modified": False,
        "stored_cognitive_packet_modified": False,
    }
    return {"context": rendered, "receipt": receipt}
