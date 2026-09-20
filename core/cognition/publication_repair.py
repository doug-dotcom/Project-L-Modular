"""Layer 68 — publication-repair quality gate.

Layer 67 gives Deep Recall one bounded regeneration attempt after the citation
integrity gate withholds content. Layer 68 makes that retry fail-safe: a repair
is publishable only when the evaluated result is measurably better than the
already-sanitised first pass.

The gate compares only post-evaluation audit metrics. It never trusts raw model
claims about quality and it never widens the frozen evidence set.
"""
from __future__ import annotations

from typing import Any


_STATUS_RANK = {
    "blocked": 0,
    "no_citations_to_check": 1,
    "partial": 2,
    "citation_checks_passed": 3,
}


def _bounded_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def publication_quality(audit: dict | None) -> tuple[int, int, int, int]:
    """Return a deterministic quality tuple for an evaluated answer.

    Higher is better. Status dominates, then fewer withheld blocks, then more
    checked citations, then more successfully published blocks.
    """
    audit = dict(audit or {})
    status_rank = _STATUS_RANK.get(str(audit.get("status") or ""), -1)
    withheld = _bounded_int(audit.get("blocks_withheld"))
    citations = _bounded_int(audit.get("citations_checked"))
    blocks = _bounded_int(audit.get("blocks_checked"))
    published = max(0, blocks - withheld)
    return status_rank, -withheld, citations, published


def choose_publication_repair(
    first_reply: str,
    first_audit: dict,
    repaired_reply: str,
    repaired_audit: dict,
) -> tuple[str, dict]:
    """Keep a Layer 67 repair only when its audited quality improves.

    The first reply has already passed through the citation gate, so it is the
    safe fallback. A non-empty retry is not sufficient evidence of improvement.
    """
    baseline = dict(first_audit or {})
    candidate = dict(repaired_audit or {})
    first_quality = publication_quality(baseline)
    repair_quality = publication_quality(candidate)

    metadata = {
        "repair_attempted": True,
        "repair_candidate_status": candidate.get("status"),
        "repair_candidate_quality": list(repair_quality),
        "first_pass_status": baseline.get("status"),
        "first_pass_quality": list(first_quality),
    }

    if not str(repaired_reply or "").strip():
        baseline.update(metadata)
        baseline.update(
            repair_accepted=False,
            repair_rejection_reason="empty_repair",
        )
        return first_reply, baseline

    if repair_quality <= first_quality:
        baseline.update(metadata)
        baseline.update(
            repair_accepted=False,
            repair_rejection_reason="quality_not_improved",
        )
        return first_reply, baseline

    candidate.update(metadata)
    candidate.update(
        repair_accepted=True,
        repair_acceptance_reason="audited_quality_improved",
    )
    return repaired_reply, candidate
