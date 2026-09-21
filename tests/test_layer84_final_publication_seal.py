from hashlib import sha256
from pathlib import Path

import pytest

from core.cognition.publication_repair import (
    FINAL_PUBLICATION_STAGES,
    final_publication_stage_receipt,
    seal_final_publication_reply,
    verify_final_publication_seal,
)


def h(text):
    return sha256(str(text).encode("utf-8")).hexdigest()


def evidence_audit(reply):
    return {
        "status": "citation_checks_passed",
        "reply_sha256": h(reply),
    }


def full_stage_chain(base, architecture, causal, final):
    return [
        final_publication_stage_receipt(
            "architecture_grounding",
            base,
            architecture,
        ),
        final_publication_stage_receipt(
            "causal_grounding",
            architecture,
            causal,
        ),
        final_publication_stage_receipt(
            "coverage_notice",
            causal,
            final,
        ),
    ]


def test_layer84_exact_allowed_stage_chain_seals_final_reply():
    base = "Audited answer"
    architecture = base + "\n\nVerified runtime"
    causal = architecture
    final = causal + "\n\nCoverage notice"
    stages = full_stage_chain(base, architecture, causal, final)

    seal = seal_final_publication_reply(
        base,
        final,
        evidence_audit(base),
        stages,
    )

    assert seal["valid"] is True
    assert seal["status"] == "sealed"
    assert seal["stage_count"] == 3
    assert [item["stage"] for item in seal["stages"]] == list(
        FINAL_PUBLICATION_STAGES
    )
    assert seal["audited_reply_sha256"] == h(base)
    assert seal["final_reply_sha256"] == h(final)
    assert len(seal["receipt_sha256"]) == 64


def test_layer84_unchanged_postprocessors_are_still_recorded_and_sealed():
    base = "Audited answer"
    stages = full_stage_chain(base, base, base, base)

    seal = seal_final_publication_reply(
        base,
        base,
        evidence_audit(base),
        stages,
    )

    assert seal["valid"] is True
    assert all(item["changed"] is False for item in stages)


def test_layer84_rejects_missing_or_reordered_postprocessor_stage():
    base = "Audited answer"
    stages = [
        final_publication_stage_receipt(
            "causal_grounding",
            base,
            base,
        ),
        final_publication_stage_receipt(
            "coverage_notice",
            base,
            base,
        ),
    ]

    seal = seal_final_publication_reply(
        base,
        base,
        evidence_audit(base),
        stages,
    )

    assert seal["valid"] is False
    assert "final_publication_stage_order_mismatch" in seal["issues"]


def test_layer84_rejects_tampered_stage_receipt():
    base = "Audited answer"
    stages = full_stage_chain(base, base, base, base)
    stages[1]["after_sha256"] = "9" * 64

    seal = seal_final_publication_reply(
        base,
        base,
        evidence_audit(base),
        stages,
    )

    assert seal["valid"] is False
    assert "causal_grounding_receipt_invalid" in seal["issues"]
    assert "coverage_notice_chain_mismatch" in seal["issues"]


def test_layer84_rejects_base_reply_not_matching_citation_audit():
    base = "Audited answer"
    stages = full_stage_chain(base, base, base, base)
    wrong_audit = evidence_audit("Different audited reply")

    seal = seal_final_publication_reply(
        base,
        base,
        wrong_audit,
        stages,
    )

    assert seal["valid"] is False
    assert "audited_reply_hash_mismatch" in seal["issues"]


def test_layer84_rejects_final_reply_changed_outside_allowed_stage_chain():
    base = "Audited answer"
    allowed_final = base + "\n\nCoverage notice"
    stages = full_stage_chain(base, base, base, allowed_final)
    mutated_final = allowed_final + "\n\nUnaudited mutation"

    seal = seal_final_publication_reply(
        base,
        mutated_final,
        evidence_audit(base),
        stages,
    )

    assert seal["valid"] is False
    assert "final_reply_chain_mismatch" in seal["issues"]


def test_layer84_post_seal_verifier_detects_late_reply_mutation():
    base = "Audited answer"
    final = base + "\n\nCoverage notice"
    stages = full_stage_chain(base, base, base, final)
    seal = seal_final_publication_reply(
        base,
        final,
        evidence_audit(base),
        stages,
    )

    check = verify_final_publication_seal(
        final + "\nlate change",
        seal,
    )

    assert check["valid"] is False
    assert "final_publication_reply_changed_after_seal" in check["issues"]


def test_layer84_post_seal_verifier_rejects_tampered_seal_receipt():
    base = "Audited answer"
    stages = full_stage_chain(base, base, base, base)
    seal = seal_final_publication_reply(
        base,
        base,
        evidence_audit(base),
        stages,
    )
    seal["status"] = "tampered"

    check = verify_final_publication_seal(base, seal)

    assert check["valid"] is False
    assert "final_publication_seal_receipt_invalid" in check["issues"]
    assert "final_publication_seal_not_valid" in check["issues"]


def test_layer84_unknown_postprocessor_name_is_rejected():
    with pytest.raises(ValueError, match="final_publication_stage_invalid"):
        final_publication_stage_receipt(
            "arbitrary_mutation",
            "before",
            "after",
        )


def test_layer84_live_server_seals_before_reflection_and_rechecks_before_writes():
    source = (Path(__file__).resolve().parents[1] / "api" / "server.py").read_text(
        encoding="utf-8"
    )

    architecture_idx = source.index('"architecture_grounding"')
    causal_idx = source.index('"causal_grounding"')
    notice_idx = source.index('"coverage_notice"')
    seal_idx = source.index("seal_final_publication_reply(")
    immediate_verify_idx = source.index(
        "immediate_seal_check = verify_final_publication_seal("
    )
    reflection_idx = source.index("reflection = reflect_on_task(")
    prewrite_verify_idx = source.index(
        "final_seal_check = verify_final_publication_seal("
    )
    working_memory_idx = source.index(
        'cognitive_packet["working_memory"] = active_context_service.complete_turn('
    )
    short_term_idx = source.index("short_term_assistant = write_live_short_term(")
    raw_write_idx = source.index(
        'write_raw_catchall(\n        "assistant",'
    )

    assert architecture_idx < causal_idx < notice_idx < seal_idx
    assert seal_idx < immediate_verify_idx < reflection_idx
    assert reflection_idx < prewrite_verify_idx < working_memory_idx
    assert working_memory_idx < short_term_idx < raw_write_idx
    assert (
        "I couldn't verify the final publication chain"
        in source
    )
    assert (
        "I couldn't verify that the final answer remained unchanged"
        in source
    )


def test_layer84_evaluation_manifest_exposes_final_publication_seal():
    source = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "cognition"
        / "evidence_evaluation.py"
    ).read_text(encoding="utf-8")

    assert 'VERSION = "2.5"' in source
    assert '"final_publication_reply_seal"' in source
