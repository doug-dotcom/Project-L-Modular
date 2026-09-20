import json
from types import SimpleNamespace

from core.cognition.publication_repair import (
    choose_publication_repair,
    coverage_contract,
    evaluate_publication_coverage,
)
from layers.layer66_deep_recall_composition_manifest import install as install_layer66


BOUND_MANIFEST = {
    "represented_parts": ["recovery timeline", "current direction"],
    "part_sources": {
        "recovery timeline": ["raw_catchall:1", "episodic_memories:2"],
        "current direction": ["memory_project_l:9"],
    },
}


def audit(*checks, status="citation_checks_passed"):
    return {
        "status": status,
        "blocks_checked": len(checks),
        "blocks_withheld": sum(not item.get("passed") for item in checks),
        "citations_checked": sum(
            len(item.get("citations", []))
            for item in checks
            if item.get("passed")
        ),
        "checks": list(checks),
    }


def passed(block, *sources):
    return {
        "block": block,
        "kind": "fact",
        "passed": True,
        "issues": [],
        "citations": [{"source": source} for source in sources],
    }


def answer(*blocks):
    return json.dumps({"blocks": list(blocks)})


def fact(text, covers):
    return {
        "kind": "fact",
        "text": text,
        "covers": covers,
        "citations": [],
    }


def test_layer70_coverage_requires_a_validated_source_bound_to_that_part():
    raw = answer(
        fact("Timeline fact.", ["recovery timeline"]),
        fact("Direction fact.", ["current direction"]),
    )
    coverage = evaluate_publication_coverage(
        raw,
        audit(
            passed(1, "raw_catchall:1"),
            passed(2, "memory_project_l:9"),
        ),
        BOUND_MANIFEST,
    )

    assert coverage["evidence_bound"] is True
    assert coverage["status"] == "complete"
    assert coverage["covered_parts"] == ["recovery timeline", "current direction"]
    assert coverage["source_mismatches"] == []


def test_layer70_rejects_spoofed_cover_label_with_unrelated_valid_citation():
    raw = answer(
        fact("This fact is valid, but it belongs to another part.", ["recovery timeline"]),
    )
    coverage = evaluate_publication_coverage(
        raw,
        audit(passed(1, "memory_project_l:9")),
        BOUND_MANIFEST,
    )

    assert coverage["status"] == "partial"
    assert coverage["covered_parts"] == []
    assert coverage["missing_parts"] == ["recovery timeline", "current direction"]
    assert coverage["source_mismatch_count"] == 1
    mismatch = coverage["source_mismatches"][0]
    assert mismatch["part"] == "recovery timeline"
    assert mismatch["cited_sources"] == ["memory_project_l:9"]
    assert "raw_catchall:1" in mismatch["allowed_sources"]


def test_layer70_allows_multi_source_block_when_one_validated_source_matches_binding():
    raw = answer(
        fact("Timeline synthesis.", ["recovery timeline"]),
    )
    coverage = evaluate_publication_coverage(
        raw,
        audit(passed(1, "memory_project_l:9", "episodic_memories:2")),
        BOUND_MANIFEST,
    )

    assert coverage["covered_parts"] == ["recovery timeline"]
    assert coverage["source_mismatch_count"] == 0


def test_layer70_contract_exposes_only_frozen_part_source_bindings():
    contract = coverage_contract(BOUND_MANIFEST)
    assert "LAYER 70 EVIDENCE BINDING" in contract
    assert "raw_catchall:1" in contract
    assert "memory_project_l:9" in contract
    assert "Do not attach a part label to an unrelated fact" in contract


def test_layer70_preserves_layer69_compatibility_when_binding_map_is_absent():
    manifest = {"represented_parts": ["recovery timeline"]}
    raw = answer(fact("Timeline.", ["recovery timeline"]))
    coverage = evaluate_publication_coverage(
        raw,
        audit(passed(1, "unrelated:7")),
        manifest,
    )

    assert coverage["evidence_bound"] is False
    assert coverage["status"] == "complete"
    assert coverage["covered_parts"] == ["recovery timeline"]


def test_layer70_repair_gate_rejects_source_binding_regression():
    first_audit = audit(passed(1, "raw_catchall:1"))
    repaired_audit = audit(
        passed(1, "raw_catchall:1"),
        passed(2, "memory_project_l:9"),
    )
    first_coverage = {
        "status": "complete",
        "complete": True,
        "covered_count": 2,
        "missing_count": 0,
        "source_mismatch_count": 0,
    }
    repaired_coverage = {
        "status": "partial",
        "complete": False,
        "covered_count": 1,
        "missing_count": 1,
        "source_mismatch_count": 1,
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


class FakeRhee:
    def __init__(self):
        self.build_context_packet = lambda _query: {
            "context": "existing context",
            "evidence": [
                {
                    "source": "raw_catchall:1",
                    "quote_source": "Recovery timeline included detox and meetings.",
                    "role": "user",
                },
                {
                    "source": "raw_catchall:2",
                    "quote_source": "Recovery timeline later included sponsor work.",
                    "role": "user",
                },
                {
                    "source": "raw_catchall:99",
                    "quote_source": "Unrelated finance note.",
                    "role": "user",
                },
            ],
            "recall_plan": {
                "deep_recall_evidence_freeze": "frozen",
                "deep_recall_presentation_question_parts": ["recovery timeline"],
                "deep_recall_presentation_represented_parts": ["recovery timeline"],
                "deep_recall_presentation_thin_parts": [],
                # Simulate Layer 38 having run before a late source existed.
                "deep_recall_final_component_sources": {
                    "recovery timeline": ["raw_catchall:1"],
                },
            },
        }

    @staticmethod
    def safe_text(value):
        return "" if value is None else str(value)

    @staticmethod
    def term_in_text(term, text):
        return term.lower() in text.lower()

    @staticmethod
    def calculate_raw_score(row, part):
        words = [word for word in part.lower().split() if len(word) > 2]
        content = str(row.get("content", "")).lower()
        return sum(word in content for word in words)


def test_layer70_manifest_recomputes_bindings_from_actual_frozen_packet():
    rhee = FakeRhee()
    install_layer66(rhee)

    packet = rhee.build_context_packet("Deep recall my recovery timeline")
    manifest = packet["recall_plan"]["deep_recall_composition_manifest_data"]

    assert packet["recall_plan"]["deep_recall_composition_manifest_version"] == 2
    assert manifest["freeze_state"] == "frozen"
    assert manifest["part_sources"]["recovery timeline"] == [
        "raw_catchall:1",
        "raw_catchall:2",
    ]
    assert "raw_catchall:99" not in manifest["part_sources"]["recovery timeline"]


def test_layer70_layer38_retains_component_source_receipt_for_observability():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "layers" / "layer38_deep_recall_final_coverage.py").read_text(
        encoding="utf-8"
    )
    assert '"deep_recall_final_component_sources": component_sources' in source
