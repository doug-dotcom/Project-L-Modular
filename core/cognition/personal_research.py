"""Project L Layer 9: evolving personal research briefs over governed evidence.

This layer does not perform external research itself. It organises already retrieved
personal evidence and capability results into a bounded research brief: what is
known, what changed, what remains uncertain, and what evidence would move the
question forward. It never stores model-generated conclusions as facts.
"""

from __future__ import annotations

import re


PERSONAL_RESEARCH_VERSION = "1.0"
MAX_ITEMS = 8

RESEARCH_SIGNALS = (
    "research this for me", "deep research this", "build me a brief",
    "keep track of this topic", "what do we know so far", "what have we learned so far",
    "update the research", "update my research", "evolving brief", "research brief",
    "dossier", "what changed since last time", "what is still unknown",
    "what do we still need to know", "what evidence would change this",
)


def personal_research_requested(message: str) -> bool:
    text = " ".join(str(message or "").lower().split())
    return any(signal in text for signal in RESEARCH_SIGNALS)


def _clip(value: object, limit: int = 700) -> str:
    return " ".join(str(value or "").split())[:limit]


def _evidence_lines(context: str) -> list[str]:
    lines = []
    for raw in str(context or "").splitlines():
        clean = raw.strip()
        if not clean:
            continue
        if re.match(r"^\d+(?:\.\d+)?\s*\|\s*(?:memory_|local_|episodic_memories|identity_anchors)", clean, re.I):
            lines.append(clean)
        elif clean.startswith(("CAPABILITY:", "STATUS:", "RESULT:")):
            lines.append(clean)
    return lines[:MAX_ITEMS]


def build_personal_research_packet(
    message: str,
    evidence_context: str,
    confidence_evidence: dict | None = None,
    capability_packet: dict | None = None,
) -> dict:
    active = personal_research_requested(message)
    if not active:
        return {
            "engine": "personal_research_layer",
            "version": PERSONAL_RESEARCH_VERSION,
            "active": False,
            "status": "not_required",
            "known_evidence": [],
            "changes": [],
            "unknowns": [],
            "next_evidence": [],
            "governance": {
                "model_conclusions_are_facts": False,
                "automatic_persistence": False,
                "external_research_performed_here": False,
            },
        }

    evidence = _evidence_lines(evidence_context)
    confidence = confidence_evidence or {}
    capability = capability_packet or {}
    unknowns = []
    next_evidence = []

    claim_modes = confidence.get("allowed_claim_modes") or []
    if not evidence:
        unknowns.append("No traceable personal evidence was retrieved for this brief.")
        next_evidence.append("Retrieve or add a dated primary record relevant to the topic.")
    if "fact" not in claim_modes:
        unknowns.append("The current evidence does not support presenting the core conclusion as a verified fact.")
    if capability.get("handled") and capability.get("status") != "ok":
        unknowns.append("Requested external/current evidence was not successfully returned.")
        next_evidence.append("Retry the relevant external capability before updating the brief's current-state claims.")

    # The layer exposes structure, not invented synthesis. L may synthesise only from
    # the evidence packet and must keep changes vs unknowns explicit in the final reply.
    changes = []
    if any("CREATED_AT=" in item or re.search(r"20\d{2}-\d{2}-\d{2}", item) for item in evidence):
        changes.append("Dated evidence is present; compare newer records against older records before claiming change.")

    return {
        "engine": "personal_research_layer",
        "version": PERSONAL_RESEARCH_VERSION,
        "active": True,
        "status": "ready" if evidence else "evidence_gap",
        "query": _clip(message, 1000),
        "known_evidence": evidence,
        "changes": changes,
        "unknowns": unknowns[:MAX_ITEMS],
        "next_evidence": next_evidence[:MAX_ITEMS],
        "instruction": (
            "Build an evolving research brief from supplied evidence only. Separate established evidence, "
            "new changes, tentative synthesis, contradictions and unknowns. Prefer newer dated evidence when "
            "the question is about change, but do not erase legitimate history. State what additional evidence "
            "would materially change the conclusion. Do not restart from generic background if prior relevant "
            "evidence is already supplied."
        ),
        "governance": {
            "model_conclusions_are_facts": False,
            "automatic_persistence": False,
            "external_research_performed_here": False,
            "traceable_evidence_required": True,
            "contradictions_preserved": True,
            "newer_evidence_can_supersede_current_state_not_history": True,
        },
    }


__all__ = [
    "PERSONAL_RESEARCH_VERSION",
    "personal_research_requested",
    "build_personal_research_packet",
]
