"""Quinn: governed wisdom and principle curation for Project L.

Quinn does not research, decide or speak to Doug. Quinn supplies versioned
principles that RIKE may apply and L may explain.
"""

from __future__ import annotations

import re


PRINCIPLES = (
    {"id": "Q-EVIDENCE-001", "version": "1.0", "principle": "Prefer traceable evidence over confident language.", "applies_to": ("evidence", "fact", "true", "verify", "recall", "remember"), "source": "Project L truth and provenance constitution"},
    {"id": "Q-CONFLICT-001", "version": "1.0", "principle": "Preserve material contradictions until stronger evidence resolves them.", "applies_to": ("conflict", "contradiction", "different", "disagree", "wrong"), "source": "Project L memory governance doctrine"},
    {"id": "Q-PATTERN-001", "version": "1.0", "principle": "One event is evidence; a pattern requires repeated traceable observations.", "applies_to": ("again", "always", "pattern", "trend", "growth", "over time"), "source": "Brains Trust longitudinal reasoning doctrine"},
    {"id": "Q-AGENCY-001", "version": "1.0", "principle": "Doug retains authority over consequential choices; L supports rather than overrides agency.", "applies_to": ("decide", "choice", "should", "recommend", "plan", "risk"), "source": "Project L agency constitution"},
    {"id": "Q-UNCERTAINTY-001", "version": "1.0", "principle": "Confidence must reflect evidence quality, agreement, recency and missing information.", "applies_to": ("confidence", "likely", "predict", "risk", "uncertain", "forecast"), "source": "Project L confidence doctrine"},
    {"id": "Q-CURRENCY-001", "version": "1.0", "principle": "Time-sensitive, legal, medical and financial claims require current authoritative verification.", "applies_to": ("current", "latest", "legal", "law", "medical", "finance", "market", "today"), "source": "Project L external research doctrine"},
)


def curate_principles(question: str, limit: int = 4) -> dict:
    text = str(question or "").lower()
    selected = [
        {key: value for key, value in item.items() if key != "applies_to"}
        for item in PRINCIPLES
        if any(signal in text for signal in item["applies_to"])
    ]
    if not selected:
        selected = [{key: value for key, value in PRINCIPLES[0].items() if key != "applies_to"}]
    return {
        "engine": "quinn",
        "version": "2.0",
        "status": "ok",
        "principles": selected[: max(1, int(limit))],
        "authority": "advisory",
        "instruction": "Apply only relevant principles and disclose uncertainty; Quinn does not decide.",
    }


def evaluate_candidate_principle(
    candidate: str,
    question: str = "",
    curated_packet: dict | None = None,
) -> dict:
    """Screen candidate wisdom without granting it authority or truth status."""
    clean = " ".join(str(candidate or "").split()).strip()
    packet = curated_packet or curate_principles(f"{question} {clean}")
    words = re.findall(r"[a-z0-9']+", clean.lower())
    overgeneralised = any(word in {"always", "never", "everyone", "everything"} for word in words)
    issues = []
    if len(words) < 4:
        issues.append("candidate_principle_not_substantive")
    if overgeneralised:
        issues.append("candidate_principle_overgeneralised")
    if packet.get("authority") != "advisory" or not packet.get("principles"):
        issues.append("quinn_review_unavailable")
    return {
        "engine": "quinn",
        "version": "3.0",
        "status": "reviewed" if not issues else "revision_required",
        "passed": not issues,
        "issues": issues,
        "candidate_principle": clean[:1200],
        "relevant_principle_ids": [
            item.get("id") for item in packet.get("principles", []) if item.get("id")
        ],
        "authority": "advisory",
    }


def run_quinn(question: str) -> dict:
    """Compatibility entrypoint for callers of the retired query-planner API."""
    return curate_principles(question)


if __name__ == "__main__":
    import json
    print(json.dumps(run_quinn("Should I trust this pattern?"), indent=2))
