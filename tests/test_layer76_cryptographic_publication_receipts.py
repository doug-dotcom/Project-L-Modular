from hashlib import sha256

from core.cognition.claim_support import bind_claim_support_to_publication
from core.cognition.publication_repair import (
    choose_publication_repair,
    publication_receipt_integrity,
)


def h(text):
    return sha256(text.encode()).hexdigest()


def support_receipt(raw, publication_raw=None, status="passed"):
    receipt = {
        "status": status,
        "draft_sha256": h(raw),
        "citation_audit_draft_sha256": h(raw),
        "publication_draft_sha256": "",
        "failed_blocks": [],
        "conflict_blocks": [],
        "compound_blocks": [],
    }
    return bind_claim_support_to_publication(
        receipt,
        publication_raw if publication_raw is not None else raw,
    )


def audit(reply, raw, *, status="citation_checks_passed", citations=2, support=None):
    result = {
        "status": status,
        "blocks_checked": 2,
        "blocks_withheld": 0 if status == "citation_checks_passed" else 1,
        "citations_checked": citations,
        "checks": [],
        "draft_sha256": h(raw),
        "reply_sha256": h(reply),
    }
    if support is not None:
        result["claim_support"] = support
    return result


def coverage(raw, *, complete=True):
    return {
        "status": "complete" if complete else "partial",
        "complete": complete,
        "covered_count": 2 if complete else 1,
        "missing_count": 0 if complete else 1,
        "draft_sha256": h(raw),
    }


def test_layer76_valid_receipt_chain_passes_integrity():
    raw = '{"blocks":[]}'
    reply = "rendered"
    receipt = publication_receipt_integrity(
        reply,
        audit(reply, raw, support=support_receipt(raw)),
        coverage(raw),
    )

    assert receipt["valid"] is True
    assert receipt["issues"] == []


def test_layer76_rejects_repair_when_rendered_reply_hash_is_stale():
    first_raw = '{"blocks":[{"kind":"unknown","text":"first"}]}'
    repair_raw = '{"blocks":[{"kind":"fact","text":"repair"}]}'
    first = audit(
        "first",
        first_raw,
        status="partial",
        citations=1,
        support=support_receipt(first_raw),
    )
    repaired = audit(
        "different repair text",
        repair_raw,
        citations=3,
        support=support_receipt(repair_raw),
    )

    reply, final = choose_publication_repair(
        "first",
        first,
        "repair",
        repaired,
        first_coverage=coverage(first_raw, complete=False),
        repaired_coverage=coverage(repair_raw),
    )

    assert reply == "first"
    assert final["repair_rejection_reason"] == "repair_receipt_mismatch"
    assert "reply_hash_mismatch" in final["repair_candidate_receipt_integrity"]["issues"]


def test_layer76_rejects_coverage_receipt_for_different_publication_draft():
    first_raw = '{"blocks":[{"kind":"unknown","text":"first"}]}'
    repair_raw = '{"blocks":[{"kind":"fact","text":"repair"}]}'
    first = audit(
        "first",
        first_raw,
        status="partial",
        citations=1,
        support=support_receipt(first_raw),
    )
    repaired = audit(
        "repair",
        repair_raw,
        citations=3,
        support=support_receipt(repair_raw),
    )
    wrong_coverage = coverage('{"blocks":[{"kind":"fact","text":"other"}]}')

    reply, final = choose_publication_repair(
        "first",
        first,
        "repair",
        repaired,
        first_coverage=coverage(first_raw, complete=False),
        repaired_coverage=wrong_coverage,
    )

    assert reply == "first"
    assert final["repair_rejection_reason"] == "repair_receipt_mismatch"
    assert "coverage_draft_mismatch" in final["repair_candidate_receipt_integrity"]["issues"]


def test_layer76_rejects_semantic_receipt_from_different_pre_gate_draft():
    raw = '{"blocks":[{"kind":"fact","text":"repair"}]}'
    bad_support = support_receipt(raw)
    bad_support["citation_audit_draft_sha256"] = h("different raw")

    receipt = publication_receipt_integrity(
        "repair",
        audit("repair", raw, support=bad_support),
        coverage(raw),
    )

    assert receipt["valid"] is False
    assert "claim_support_source_draft_mismatch" in receipt["issues"]


def test_layer76_rejects_semantic_receipt_bound_to_different_publication():
    raw = '{"blocks":[{"kind":"fact","text":"repair"}]}'
    support = support_receipt(raw, publication_raw="different publication")

    receipt = publication_receipt_integrity(
        "repair",
        audit("repair", raw, support=support),
        coverage(raw),
    )

    assert receipt["valid"] is False
    assert "claim_support_publication_draft_mismatch" in receipt["issues"]


def test_layer76_first_pass_mismatch_blocks_quality_comparison():
    raw = '{"blocks":[{"kind":"fact","text":"first"}]}'
    first = audit("not-first", raw, support=support_receipt(raw))
    repaired = audit("repair", raw, citations=4, support=support_receipt(raw))

    reply, final = choose_publication_repair(
        "first",
        first,
        "repair",
        repaired,
        first_coverage=coverage(raw),
        repaired_coverage=coverage(raw),
    )

    assert reply == "first"
    assert final["repair_rejection_reason"] == "first_pass_receipt_mismatch"


def test_layer76_legacy_unhashed_audits_remain_compatible():
    first = {
        "status": "partial",
        "blocks_checked": 2,
        "blocks_withheld": 1,
        "citations_checked": 1,
        "checks": [],
    }
    repaired = {
        "status": "citation_checks_passed",
        "blocks_checked": 2,
        "blocks_withheld": 0,
        "citations_checked": 2,
        "checks": [],
    }

    reply, final = choose_publication_repair(
        "first",
        first,
        "repair",
        repaired,
        first_coverage={
            "status": "partial",
            "complete": False,
            "covered_count": 1,
            "missing_count": 1,
        },
        repaired_coverage={
            "status": "complete",
            "complete": True,
            "covered_count": 2,
            "missing_count": 0,
        },
    )

    assert reply == "repair"
    assert final["repair_accepted"] is True


def test_layer76_live_server_binds_both_semantic_receipts_to_publication():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "api" / "server.py").read_text(encoding="utf-8")

    assert source.count("bind_claim_support_to_publication(") >= 2
    assert "first_support = bind_claim_support_to_publication" in source
    assert "repaired_support = bind_claim_support_to_publication" in source


def test_layer76_coverage_receipt_hash_is_emitted_by_live_evaluator():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (
        root / "core" / "cognition" / "publication_repair.py"
    ).read_text(encoding="utf-8")

    assert '"draft_sha256": sha256(str(raw or "").encode()).hexdigest()' in source
    assert '"repair_candidate_receipt_integrity"' in source
    assert '"first_pass_receipt_integrity"' in source
