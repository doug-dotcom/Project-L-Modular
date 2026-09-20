import json

from core.cognition.publication_repair import (
    choose_publication_repair,
    evaluate_publication_coverage,
    verify_frozen_evidence_binding,
)
from layers.layer66_deep_recall_composition_manifest import install as install_layer66


ROWS = [
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
]


class FakeRhee:
    def __init__(self, rows=None):
        self.rows = list(rows or ROWS)
        self.build_context_packet = lambda _query: {
            "context": "existing context",
            "evidence": list(self.rows),
            "recall_plan": {
                "deep_recall_evidence_freeze": "frozen",
                "deep_recall_presentation_question_parts": ["recovery timeline"],
                "deep_recall_presentation_represented_parts": ["recovery timeline"],
                "deep_recall_presentation_thin_parts": [],
                "deep_recall_final_component_sources": {
                    "recovery timeline": ["raw_catchall:1", "raw_catchall:2"],
                },
                "deep_recall_evidence_freeze_final_readiness": "ready",
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


def built_manifest(rows=None):
    rhee = FakeRhee(rows)
    install_layer66(rhee)
    packet = rhee.build_context_packet("Deep recall my recovery timeline")
    return (
        packet["recall_plan"]["deep_recall_composition_manifest_data"],
        packet["evidence"],
        packet["recall_plan"]["deep_recall_composition_manifest_version"],
    )


def citation_audit():
    return {
        "status": "citation_checks_passed",
        "blocks_checked": 1,
        "blocks_withheld": 0,
        "citations_checked": 1,
        "checks": [
            {
                "block": 1,
                "kind": "fact",
                "passed": True,
                "issues": [],
                "citations": [{"source": "raw_catchall:1"}],
            }
        ],
    }


def simple_coverage(binding):
    return {
        "status": "complete",
        "complete": True,
        "covered_count": 1,
        "missing_count": 0,
        "frozen_evidence_binding": binding,
    }


def test_layer77_manifest_fingerprints_exact_frozen_packet_and_itself():
    manifest, rows, version = built_manifest()
    binding = verify_frozen_evidence_binding(manifest, rows)

    assert version == 4
    assert len(manifest["manifest_sha256"]) == 64
    assert len(manifest["evidence_packet_sha256"]) == 64
    assert binding["valid"] is True
    assert binding["status"] == "verified"
    assert binding["actual_manifest_sha256"] == manifest["manifest_sha256"]
    assert binding["actual_evidence_packet_sha256"] == manifest["evidence_packet_sha256"]


def test_layer77_mutated_evidence_excerpt_fails_closed():
    manifest, rows, _version = built_manifest()
    mutated = [dict(item) for item in rows]
    mutated[0]["quote_source"] = "Mutated evidence text."

    binding = verify_frozen_evidence_binding(manifest, mutated)

    assert binding["valid"] is False
    assert "evidence_packet_fingerprint_mismatch" in binding["issues"]


def test_layer77_reordered_evidence_packet_fails_because_prompt_order_is_frozen():
    manifest, rows, _version = built_manifest()

    binding = verify_frozen_evidence_binding(manifest, list(reversed(rows)))

    assert binding["valid"] is False
    assert "evidence_packet_fingerprint_mismatch" in binding["issues"]


def test_layer77_tampered_manifest_field_fails_manifest_fingerprint():
    manifest, rows, _version = built_manifest()
    tampered = dict(manifest)
    tampered["readiness"] = "tampered"

    binding = verify_frozen_evidence_binding(tampered, rows)

    assert binding["valid"] is False
    assert "manifest_fingerprint_mismatch" in binding["issues"]


def test_layer77_coverage_gate_blocks_mismatched_frozen_packet_before_coverage():
    manifest, rows, _version = built_manifest()
    mutated = [dict(item) for item in rows]
    mutated[1]["quote_source"] = "Different sponsor record."
    raw = json.dumps({
        "blocks": [{
            "kind": "fact",
            "text": "Recovery included detox.",
            "covers": ["recovery timeline"],
            "citations": [],
        }]
    })

    coverage = evaluate_publication_coverage(
        raw,
        citation_audit(),
        manifest,
        evidence_rows=mutated,
    )

    assert coverage["status"] == "blocked"
    assert coverage["complete"] is False
    assert coverage["frozen_evidence_binding"]["valid"] is False


def test_layer77_repair_selector_rejects_coverage_from_different_frozen_binding():
    manifest, rows, _version = built_manifest()
    expected = verify_frozen_evidence_binding(manifest, rows)

    other_rows = [dict(item) for item in rows]
    other_rows[0]["quote_source"] = "Different frozen evidence."
    other_manifest, other_packet, _version = built_manifest(other_rows)
    other = verify_frozen_evidence_binding(other_manifest, other_packet)

    first_audit = {
        "status": "partial",
        "blocks_checked": 1,
        "blocks_withheld": 1,
        "citations_checked": 0,
        "checks": [],
    }
    repaired_audit = {
        "status": "citation_checks_passed",
        "blocks_checked": 1,
        "blocks_withheld": 0,
        "citations_checked": 1,
        "checks": [],
    }

    reply, final = choose_publication_repair(
        "first",
        first_audit,
        "repair",
        repaired_audit,
        first_coverage=simple_coverage(expected),
        repaired_coverage=simple_coverage(other),
        frozen_binding=expected,
    )

    assert reply == "first"
    assert final["repair_accepted"] is False
    assert final["repair_rejection_reason"] == "repair_receipt_mismatch"
    issues = final["repair_candidate_receipt_integrity"]["issues"]
    assert (
        "coverage_manifest_binding_mismatch" in issues
        or "coverage_evidence_binding_mismatch" in issues
    )


def test_layer77_legacy_manifest_without_fingerprints_remains_compatible():
    legacy = {
        "represented_parts": ["recovery timeline"],
        "part_sources": {"recovery timeline": ["raw_catchall:1"]},
    }

    binding = verify_frozen_evidence_binding(legacy, ROWS)

    assert binding["valid"] is True
    assert binding["status"] == "legacy_unbound"


def test_layer77_manifest_fingerprint_changes_when_binding_contract_changes():
    manifest, rows, _version = built_manifest()
    first = verify_frozen_evidence_binding(manifest, rows)

    changed = dict(manifest)
    changed["part_sources"] = {
        "recovery timeline": ["raw_catchall:2"],
    }
    second = verify_frozen_evidence_binding(changed, rows)

    assert first["valid"] is True
    assert second["valid"] is False
    assert second["actual_manifest_sha256"] != first["actual_manifest_sha256"]


def test_layer77_live_server_preflights_frozen_binding_and_passes_it_to_repair_gate():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "api" / "server.py").read_text(encoding="utf-8")

    assert "verify_frozen_evidence_binding(" in source
    assert '"reason": "frozen_evidence_binding_mismatch"' in source
    assert "so I've withheld it. Please try again." in source
    assert "frozen_binding=frozen_evidence_binding" in source
