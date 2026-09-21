from core.cognition.publication_repair import (
    choose_publication_repair,
    publication_quality,
)


def audit(status, withheld=0, citations=0, blocks=1):
    return {
        "status": status,
        "blocks_withheld": withheld,
        "citations_checked": citations,
        "blocks_checked": blocks,
    }


def test_layer68_rejects_worse_repair_and_keeps_safe_first_pass():
    first = "First pass kept one verified stage."
    repaired = "Repair lost everything."
    reply, final_audit = choose_publication_repair(
        first,
        audit("partial", withheld=1, citations=2, blocks=3),
        repaired,
        audit("blocked", withheld=1, citations=0, blocks=1),
    )

    assert reply == first
    assert final_audit["repair_attempted"] is True
    assert final_audit["repair_accepted"] is False
    assert final_audit["repair_rejection_reason"] == "citation_quality_regressed"
    assert final_audit["repair_candidate_status"] == "blocked"


def test_layer68_accepts_repair_that_clears_citation_gate():
    first = "One stage was withheld."
    repaired = "All supported stages now publish."
    reply, final_audit = choose_publication_repair(
        first,
        audit("partial", withheld=1, citations=2, blocks=3),
        repaired,
        audit("citation_checks_passed", withheld=0, citations=4, blocks=4),
    )

    assert reply == repaired
    assert final_audit["repair_accepted"] is True
    assert final_audit["repair_acceptance_reason"] == "audited_quality_improved"
    assert final_audit["status"] == "citation_checks_passed"


def test_layer68_accepts_partial_repair_only_when_withholding_improves():
    first = "Two supported stages were withheld."
    repaired = "Only one stage remains withheld."
    reply, final_audit = choose_publication_repair(
        first,
        audit("partial", withheld=2, citations=2, blocks=5),
        repaired,
        audit("partial", withheld=1, citations=2, blocks=5),
    )

    assert reply == repaired
    assert final_audit["repair_accepted"] is True


def test_layer68_rejects_equal_quality_churn():
    first = "Keep the stable sanitised answer."
    repaired = "Different wording with no measured gain."
    reply, final_audit = choose_publication_repair(
        first,
        audit("partial", withheld=1, citations=3, blocks=4),
        repaired,
        audit("partial", withheld=1, citations=3, blocks=4),
    )

    assert reply == first
    assert final_audit["repair_accepted"] is False


def test_layer68_rejects_empty_repair_even_if_audit_claims_improvement():
    first = "Verified fallback."
    reply, final_audit = choose_publication_repair(
        first,
        audit("blocked", withheld=1, citations=0, blocks=1),
        "   ",
        audit("citation_checks_passed", withheld=0, citations=3, blocks=3),
    )

    assert reply == first
    assert final_audit["repair_rejection_reason"] == "empty_repair"


def test_layer68_quality_order_prefers_citation_integrity_then_less_withholding():
    assert publication_quality(audit("citation_checks_passed", 0, 1, 1)) > publication_quality(
        audit("partial", 0, 99, 99)
    )
    assert publication_quality(audit("partial", 1, 2, 4)) > publication_quality(
        audit("partial", 2, 50, 50)
    )
