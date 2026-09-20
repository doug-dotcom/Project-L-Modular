"""Layers 68–70 — publication repair quality and coverage gates.

Layer 67 gives Deep Recall one bounded regeneration attempt after the citation
integrity gate withholds content. Layer 68 makes that retry fail-safe: a repair
is publishable only when its evaluated citation quality improves.

Layer 69 adds structural coverage receipts. Deep Recall's frozen composition
manifest already identifies evidence-supported requested parts. The generated
JSON must now label which of those parts each publishable block covers. Repairs
may improve citation quality or structural coverage, but they may not regress
either dimension.

Layer 70 binds coverage to evidence provenance. A block may claim a frozen
represented-part label only when its validated citations include a source that
the retrieval pipeline itself associated with that part before evidence freeze.
"""

from __future__ import annotations

import json
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


def _unique_parts(values: Any) -> list[str]:
    parts = []
    seen = set()
    if not isinstance(values, list):
        return parts
    for value in values:
        label = str(value or "").strip()
        if label and label not in seen:
            parts.append(label)
            seen.add(label)
    return parts


def coverage_contract(manifest: dict | None) -> str:
    """Return the Layers 69–70 structural/evidence coverage contract."""
    manifest = dict(manifest or {})
    represented = _unique_parts(manifest.get("represented_parts"))
    if not represented:
        return "DEEP RECALL COVERAGE RECEIPT: no represented parts require structural coverage labelling."

    raw_bindings = manifest.get("part_sources")
    binding_available = isinstance(raw_bindings, dict) and all(
        part in raw_bindings for part in represented
    )
    bindings = {
        part: _unique_parts(raw_bindings.get(part))[:20]
        for part in represented
    } if binding_available else {}

    contract = (
        "DEEP RECALL COVERAGE RECEIPT — for this Deep Recall only, every answer block "
        "must include a \"covers\" array. Each covers value must be copied exactly from "
        "the represented-part labels below. A represented part counts as covered only when "
        "it appears on a block that passes the citation-integrity gate; unknown blocks do "
        "not satisfy supported-part coverage. Use [] when a block does not cover one of "
        "these parts. Do not invent or paraphrase labels. Represented parts: "
        + json.dumps(represented, ensure_ascii=False)
    )
    if binding_available:
        contract += (
            "\nLAYER 70 EVIDENCE BINDING: a covers label is valid only when that same "
            "block has a validated citation from one of the frozen supporting source IDs "
            "mapped to that represented part. Do not attach a part label to an unrelated "
            "fact merely to satisfy coverage. Frozen part-to-source bindings: "
            + json.dumps(bindings, ensure_ascii=False)
        )
    return contract


def evaluate_publication_coverage(
    raw: str,
    evidence_audit: dict | None,
    manifest: dict | None,
) -> dict:
    """Measure structural coverage using only publishable evaluated blocks.

    This is deliberately not a semantic truth detector. The model may only claim
    exact labels issued by the frozen composition manifest, and only labels on
    citation-gate-passing non-unknown blocks count toward coverage.
    """
    manifest = dict(manifest or {})
    expected = _unique_parts(manifest.get("represented_parts"))
    raw_bindings = manifest.get("part_sources")
    binding_available = isinstance(raw_bindings, dict) and all(
        part in raw_bindings for part in expected
    )
    allowed_sources = {
        part: set(_unique_parts(raw_bindings.get(part)))
        for part in expected
    } if binding_available else {}

    audit = {
        "version": "2.0" if binding_available else "1.0",
        "status": "not_required" if not expected else "partial",
        "expected_parts": expected,
        "expected_count": len(expected),
        "covered_parts": [],
        "covered_count": 0,
        "missing_parts": list(expected),
        "missing_count": len(expected),
        "invalid_labels": [],
        "invalid_blocks": [],
        "evidence_bound": binding_available,
        "source_mismatches": [],
        "complete": not expected,
    }
    if not expected:
        return audit

    passed_blocks = set()
    passed_block_sources = {}
    for item in (evidence_audit or {}).get("checks", []):
        if not isinstance(item, dict) or not item.get("passed"):
            continue
        number = _bounded_int(item.get("block"))
        passed_blocks.add(number)
        passed_block_sources[number] = {
            str(citation.get("source") or "").strip()
            for citation in item.get("citations", [])
            if isinstance(citation, dict) and citation.get("source")
        }

    try:
        data = json.loads(raw)
        blocks = data.get("blocks")
        if not isinstance(blocks, list):
            raise ValueError("invalid_blocks")
    except (ValueError, TypeError, json.JSONDecodeError):
        audit["invalid_blocks"] = ["invalid_answer_schema"]
        return audit

    expected_set = set(expected)
    covered = []
    covered_set = set()
    invalid_labels = []
    invalid_blocks = []
    source_mismatches = []

    for number, block in enumerate(blocks, 1):
        if number not in passed_blocks or not isinstance(block, dict):
            continue
        if block.get("kind") == "unknown":
            continue

        covers = block.get("covers", [])
        if not isinstance(covers, list):
            invalid_blocks.append(number)
            continue

        for value in covers:
            label = str(value or "").strip()
            if not label:
                continue
            if label not in expected_set:
                if label not in invalid_labels:
                    invalid_labels.append(label)
                continue

            if binding_available:
                cited_sources = passed_block_sources.get(number, set())
                permitted_sources = allowed_sources.get(label, set())
                if not cited_sources.intersection(permitted_sources):
                    source_mismatches.append({
                        "block": number,
                        "part": label,
                        "cited_sources": sorted(cited_sources)[:8],
                        "allowed_sources": sorted(permitted_sources)[:12],
                    })
                    continue

            if label not in covered_set:
                covered.append(label)
                covered_set.add(label)

    missing = [part for part in expected if part not in covered_set]
    audit.update(
        status="complete" if not missing else "partial",
        covered_parts=covered,
        covered_count=len(covered),
        missing_parts=missing,
        missing_count=len(missing),
        invalid_labels=invalid_labels,
        invalid_blocks=invalid_blocks,
        source_mismatches=source_mismatches,
        source_mismatch_count=len(source_mismatches),
        complete=not missing,
    )
    return audit


def publication_quality(audit: dict | None) -> tuple[int, int, int, int]:
    """Return a deterministic citation-quality tuple. Higher is better."""
    audit = dict(audit or {})
    status_rank = _STATUS_RANK.get(str(audit.get("status") or ""), -1)
    withheld = _bounded_int(audit.get("blocks_withheld"))
    citations = _bounded_int(audit.get("citations_checked"))
    blocks = _bounded_int(audit.get("blocks_checked"))
    published = max(0, blocks - withheld)
    return status_rank, -withheld, citations, published


def coverage_quality(coverage: dict | None) -> tuple[int, int, int, int]:
    """Return a deterministic Layer 69 coverage-quality tuple."""
    coverage = dict(coverage or {})
    if coverage.get("status") == "not_required":
        return 1, 0, 0, 0
    complete = 1 if coverage.get("complete") else 0
    covered = _bounded_int(coverage.get("covered_count"))
    missing = _bounded_int(coverage.get("missing_count"))
    invalid = (
        len(coverage.get("invalid_labels") or [])
        + len(coverage.get("invalid_blocks") or [])
        + _bounded_int(coverage.get("source_mismatch_count"))
    )
    return complete, covered, -missing, -invalid


def choose_publication_repair(
    first_reply: str,
    first_audit: dict,
    repaired_reply: str,
    repaired_audit: dict,
    *,
    first_coverage: dict | None = None,
    repaired_coverage: dict | None = None,
) -> tuple[str, dict]:
    """Keep a Layer 67 repair only when governed quality improves safely.

    Layer 68 remains the default behaviour when no coverage receipts are supplied.
    With Layers 69–70 receipts, neither citation quality nor evidence-bound
    structural coverage may regress; at least one must strictly improve.
    """
    baseline = dict(first_audit or {})
    candidate = dict(repaired_audit or {})
    first_quality = publication_quality(baseline)
    repair_quality = publication_quality(candidate)
    has_coverage = first_coverage is not None or repaired_coverage is not None
    first_coverage_quality = coverage_quality(first_coverage) if has_coverage else None
    repair_coverage_quality = coverage_quality(repaired_coverage) if has_coverage else None

    if first_coverage is not None:
        baseline["coverage"] = dict(first_coverage)
    if repaired_coverage is not None:
        candidate["coverage"] = dict(repaired_coverage)

    metadata = {
        "repair_attempted": True,
        "repair_candidate_status": candidate.get("status"),
        "repair_candidate_quality": list(repair_quality),
        "first_pass_status": baseline.get("status"),
        "first_pass_quality": list(first_quality),
    }
    if has_coverage:
        metadata.update(
            repair_candidate_coverage_quality=list(repair_coverage_quality),
            first_pass_coverage_quality=list(first_coverage_quality),
        )

    if not str(repaired_reply or "").strip():
        baseline.update(metadata)
        baseline.update(
            repair_accepted=False,
            repair_rejection_reason="empty_repair",
        )
        return first_reply, baseline

    if not has_coverage:
        if repair_quality <= first_quality:
            baseline.update(metadata)
            baseline.update(
                repair_accepted=False,
                repair_rejection_reason="quality_not_improved",
            )
            return first_reply, baseline
    else:
        if repair_quality < first_quality:
            baseline.update(metadata)
            baseline.update(
                repair_accepted=False,
                repair_rejection_reason="citation_quality_regressed",
            )
            return first_reply, baseline
        if repair_coverage_quality < first_coverage_quality:
            baseline.update(metadata)
            baseline.update(
                repair_accepted=False,
                repair_rejection_reason="coverage_regressed",
            )
            return first_reply, baseline
        if repair_quality == first_quality and repair_coverage_quality == first_coverage_quality:
            baseline.update(metadata)
            baseline.update(
                repair_accepted=False,
                repair_rejection_reason="quality_not_improved",
            )
            return first_reply, baseline

    candidate.update(metadata)
    candidate.update(
        repair_accepted=True,
        repair_acceptance_reason=(
            "audited_quality_and_coverage_nonregression"
            if has_coverage
            else "audited_quality_improved"
        ),
    )
    return repaired_reply, candidate
