import json

from core.cognition.publication_repair import (
    choose_publication_repair,
    coverage_contract,
    coverage_quality,
    evaluate_publication_coverage,
)


MANIFEST = {
    "represented_parts": [
        "recovery timeline",
        "relationship decision",
        "current direction",
    ]
}


def evidence_audit(*passed_blocks, status="citation_checks_passed", citations=3):
    checks = [
        {
            "block": number,
            "kind": "fact",
            "passed": number in passed_blocks,
            "issues": [] if number in passed_blocks else ["quote_not_in_cited_source"],
            "citations": [{"source": f"raw_catchall:{number}"}] if number in passed_blocks else [],
        }
        for number in range(1, 5)
    ]
    return {
        "status": status,
        "blocks_checked": 4,
        "blocks_withheld": sum(not item["passed"] for item in checks),
        "citations_checked": citations,
        "checks": checks,
    }


def answer(*blocks):
    return json.dumps({"blocks": list(blocks)})


def block(text, covers, kind="fact"):
    return {
        "kind": kind,
        "text": text,
        "covers": covers,
        "citations": [],
    }


def test_layer69_contract_uses_exact_frozen_represented_parts():
    contract = coverage_contract(MANIFEST)
    assert "every answer block must include a \"covers\" array" in contract
    for label in MANIFEST["represented_parts"]:
        assert label in contract
    assert "Do not invent or paraphrase labels" in contract


def test_layer69_counts_only_exact_labels_on_publishable_blocks():
    raw = answer(
        block("Timeline.", ["recovery timeline"]),
        block("Decision.", ["relationship decision"]),
        block("Direction.", ["current direction"]),
    )
    coverage = evaluate_publication_coverage(
        raw,
        evidence_audit(1, 2, 3),
        MANIFEST,
    )
    assert coverage["status"] == "complete"
    assert coverage["complete"] is True
    assert coverage["covered_count"] == 3
    assert coverage["missing_parts"] == []


def test_layer69_failed_or_unknown_blocks_cannot_fake_coverage():
    raw = answer(
        block("Timeline.", ["recovery timeline"]),
        block("Decision with bad citation.", ["relationship decision"]),
        block("I do not know.", ["current direction"], kind="unknown"),
    )
    coverage = evaluate_publication_coverage(
        raw,
        evidence_audit(1, 3),
        MANIFEST,
    )
    assert coverage["covered_parts"] == ["recovery timeline"]
    assert coverage["missing_parts"] == ["relationship decision", "current direction"]
    assert coverage["status"] == "partial"


def test_layer69_rejects_paraphrased_or_invented_coverage_labels():
    raw = answer(
        block("Timeline.", ["Recovery Timeline", "made up part"]),
        block("Decision.", ["relationship decision"]),
    )
    coverage = evaluate_publication_coverage(
        raw,
        evidence_audit(1, 2),
        MANIFEST,
    )
    assert coverage["covered_parts"] == ["relationship decision"]
    assert coverage["missing_parts"] == ["recovery timeline", "current direction"]
    assert coverage["invalid_labels"] == ["Recovery Timeline", "made up part"]


def test_layer69_accepts_equal_citation_quality_when_coverage_improves():
    first_coverage = {
        "status": "partial",
        "complete": False,
        "covered_count": 2,
        "missing_count": 1,
    }
    repaired_coverage = {
        "status": "complete",
        "complete": True,
        "covered_count": 3,
        "missing_count": 0,
    }
    audit = evidence_audit(1, 2, 3, 4)

    reply, final_audit = choose_publication_repair(
        "first",
        audit,
        "repair",
        audit,
        first_coverage=first_coverage,
        repaired_coverage=repaired_coverage,
    )
    assert reply == "repair"
    assert final_audit["repair_accepted"] is True
    assert final_audit["coverage"]["complete"] is True


def test_layer69_rejects_coverage_regression_even_when_citations_improve():
    first_audit = evidence_audit(1, 2, status="partial", citations=2)
    repaired_audit = evidence_audit(1, 2, 3, 4, status="citation_checks_passed", citations=4)
    first_coverage = {
        "status": "partial",
        "complete": False,
        "covered_count": 2,
        "missing_count": 1,
    }
    repaired_coverage = {
        "status": "partial",
        "complete": False,
        "covered_count": 1,
        "missing_count": 2,
    }

    reply, final_audit = choose_publication_repair(
        "first",
        first_audit,
        "repair",
        repaired_audit,
        first_coverage=first_coverage,
        repaired_coverage=repaired_coverage,
    )
    assert reply == "first"
    assert final_audit["repair_accepted"] is False
    assert final_audit["repair_rejection_reason"] == "coverage_regressed"


def test_layer69_quality_prefers_more_complete_structural_coverage():
    complete = {"status": "complete", "complete": True, "covered_count": 3, "missing_count": 0}
    partial = {"status": "partial", "complete": False, "covered_count": 2, "missing_count": 1}
    assert coverage_quality(complete) > coverage_quality(partial)


def test_layer69_server_wires_coverage_into_both_passes():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "api" / "server.py").read_text(encoding="utf-8")
    assert "coverage_contract(composition_manifest)" in source
    assert "first_coverage = (" in source
    assert "repaired_coverage = evaluate_publication_coverage(" in source
    assert "first_coverage=first_coverage" in source
    assert "repaired_coverage=repaired_coverage" in source
