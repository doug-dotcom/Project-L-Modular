from core.cognition.publication_repair import (
    choose_publication_repair,
    claim_support_quality,
)


def citation_audit(*, status="citation_checks_passed", blocks=2, withheld=0, citations=2, support=None):
    audit = {
        "status": status,
        "blocks_checked": blocks,
        "blocks_withheld": withheld,
        "citations_checked": citations,
        "checks": [],
    }
    if support is not None:
        audit["claim_support"] = support
    return audit


def coverage(*, complete=True, covered=2, missing=0):
    return {
        "status": "complete" if complete else "partial",
        "complete": complete,
        "covered_count": covered,
        "missing_count": missing,
    }


def support(status, failed=None, conflicts=None, compound=None):
    return {
        "status": status,
        "failed_blocks": failed or [],
        "conflict_blocks": conflicts or [],
        "compound_blocks": compound or [],
    }


def test_layer75_rejects_semantic_regression_even_when_citations_improve():
    first = citation_audit(
        status="partial",
        withheld=1,
        citations=1,
        support=support("passed"),
    )
    repaired = citation_audit(
        status="citation_checks_passed",
        withheld=0,
        citations=3,
        support=support("partial", failed=[1]),
    )

    reply, audit = choose_publication_repair(
        "first",
        first,
        "repair",
        repaired,
        first_coverage=coverage(),
        repaired_coverage=coverage(),
    )

    assert reply == "first"
    assert audit["repair_accepted"] is False
    assert audit["repair_rejection_reason"] == "claim_support_regressed"


def test_layer75_rejects_unavailable_semantic_checker_after_safe_first_pass():
    first = citation_audit(support=support("passed"))
    repaired = citation_audit(
        citations=4,
        support=support("unavailable"),
    )

    reply, audit = choose_publication_repair(
        "first",
        first,
        "repair",
        repaired,
        first_coverage=coverage(),
        repaired_coverage=coverage(),
    )

    assert reply == "first"
    assert audit["repair_rejection_reason"] == "claim_support_regressed"


def test_layer75_partial_is_safer_than_unavailable_because_failed_blocks_are_gated():
    partial = claim_support_quality(
        support("partial", failed=[1], conflicts=[1])
    )
    unavailable = claim_support_quality(support("unavailable"))

    assert partial > unavailable


def test_layer75_accepts_semantic_improvement_with_equal_citation_and_coverage():
    first = citation_audit(
        support=support("partial", failed=[1, 2], conflicts=[1, 2]),
    )
    repaired = citation_audit(
        support=support("partial", failed=[1], conflicts=[1]),
    )

    reply, audit = choose_publication_repair(
        "first",
        first,
        "repair",
        repaired,
        first_coverage=coverage(),
        repaired_coverage=coverage(),
    )

    assert reply == "repair"
    assert audit["repair_accepted"] is True
    assert audit["repair_acceptance_reason"] == (
        "audited_quality_coverage_and_claim_support_nonregression"
    )


def test_layer75_accepts_partial_to_passed_semantic_improvement():
    first = citation_audit(
        support=support("partial", failed=[1], compound=[1]),
    )
    repaired = citation_audit(support=support("passed"))

    reply, audit = choose_publication_repair(
        "first",
        first,
        "repair",
        repaired,
        first_coverage=coverage(),
        repaired_coverage=coverage(),
    )

    assert reply == "repair"
    assert audit["repair_accepted"] is True
    assert audit["repair_candidate_support_quality"] > audit["first_pass_support_quality"]


def test_layer75_rejects_new_cross_block_conflict_on_repair():
    first = citation_audit(support=support("passed"))
    repaired = citation_audit(
        citations=4,
        support=support(
            "partial",
            failed=[1, 2],
            conflicts=[1, 2],
        ),
    )

    reply, audit = choose_publication_repair(
        "first",
        first,
        "repair",
        repaired,
        first_coverage=coverage(),
        repaired_coverage=coverage(),
    )

    assert reply == "first"
    assert audit["repair_rejection_reason"] == "claim_support_regressed"


def test_layer75_rejects_new_compound_fact_on_repair():
    first = citation_audit(support=support("passed"))
    repaired = citation_audit(
        citations=3,
        support=support("partial", failed=[2], compound=[2]),
    )

    reply, audit = choose_publication_repair(
        "first",
        first,
        "repair",
        repaired,
        first_coverage=coverage(),
        repaired_coverage=coverage(),
    )

    assert reply == "first"
    assert audit["repair_rejection_reason"] == "claim_support_regressed"


def test_layer75_preserves_pre_layer72_repair_behavior_without_support_receipts():
    first = citation_audit(status="partial", withheld=1, citations=1)
    repaired = citation_audit(
        status="citation_checks_passed",
        withheld=0,
        citations=2,
    )

    reply, audit = choose_publication_repair(
        "first",
        first,
        "repair",
        repaired,
        first_coverage=coverage(complete=False, covered=1, missing=1),
        repaired_coverage=coverage(complete=True, covered=2, missing=0),
    )

    assert reply == "repair"
    assert audit["repair_accepted"] is True
    assert "repair_candidate_support_quality" not in audit


def test_layer75_equal_everything_still_rejects_churn():
    first = citation_audit(support=support("passed"))
    repaired = citation_audit(support=support("passed"))

    reply, audit = choose_publication_repair(
        "first",
        first,
        "repair",
        repaired,
        first_coverage=coverage(),
        repaired_coverage=coverage(),
    )

    assert reply == "first"
    assert audit["repair_rejection_reason"] == "quality_not_improved"
