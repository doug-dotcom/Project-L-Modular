from hashlib import sha256
from pathlib import Path

from core.cognition.publication_repair import (
    choose_publication_repair,
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
    def __init__(self):
        self.build_context_packet = lambda _query: {
            "context": "existing context",
            "evidence": list(ROWS),
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


def manifest_for(query):
    rhee = FakeRhee()
    install_layer66(rhee)
    packet = rhee.build_context_packet(query)
    return (
        packet["recall_plan"]["deep_recall_composition_manifest_data"],
        packet["evidence"],
        packet["recall_plan"]["deep_recall_composition_manifest_version"],
    )


def simple_coverage(binding):
    return {
        "status": "complete",
        "complete": True,
        "covered_count": 1,
        "missing_count": 0,
        "frozen_evidence_binding": binding,
    }


def audit(status, citations):
    return {
        "status": status,
        "blocks_checked": 1,
        "blocks_withheld": 1 if status == "partial" else 0,
        "citations_checked": citations,
        "checks": [],
    }


def test_layer78_manifest_binds_exact_deep_recall_query():
    query = "Deep recall my recovery timeline"
    manifest, rows, version = manifest_for(query)

    assert version == 5
    assert manifest["query_sha256"] == sha256(query.encode("utf-8")).hexdigest()

    binding = verify_frozen_evidence_binding(
        manifest,
        rows,
        query=query,
    )
    assert binding["valid"] is True
    assert binding["query_bound"] is True
    assert binding["query_verified"] is True
    assert binding["request_query_sha256"] == manifest["query_sha256"]


def test_layer78_different_query_fails_even_with_identical_frozen_evidence():
    original = "Deep recall my recovery timeline"
    manifest, rows, _version = manifest_for(original)

    binding = verify_frozen_evidence_binding(
        manifest,
        rows,
        query="Deep recall my Project L timeline",
    )

    assert binding["valid"] is False
    assert "request_query_fingerprint_mismatch" in binding["issues"]


def test_layer78_query_binding_is_exact_not_case_or_punctuation_fuzzy():
    original = "Deep recall my recovery timeline"
    manifest, rows, _version = manifest_for(original)

    changed_case = verify_frozen_evidence_binding(
        manifest,
        rows,
        query="deep recall my recovery timeline",
    )
    changed_punctuation = verify_frozen_evidence_binding(
        manifest,
        rows,
        query="Deep recall my recovery timeline?",
    )

    assert changed_case["valid"] is False
    assert changed_punctuation["valid"] is False


def test_layer78_same_evidence_different_query_changes_manifest_fingerprint():
    first_manifest, first_rows, _ = manifest_for(
        "Deep recall my recovery timeline"
    )
    second_manifest, second_rows, _ = manifest_for(
        "Deep recall my current recovery direction"
    )

    assert first_rows == second_rows
    assert first_manifest["evidence_packet_sha256"] == second_manifest["evidence_packet_sha256"]
    assert first_manifest["query_sha256"] != second_manifest["query_sha256"]
    assert first_manifest["manifest_sha256"] != second_manifest["manifest_sha256"]


def test_layer78_tampering_query_hash_also_breaks_manifest_fingerprint():
    query = "Deep recall my recovery timeline"
    manifest, rows, _version = manifest_for(query)
    tampered = dict(manifest)
    tampered["query_sha256"] = sha256(b"another query").hexdigest()

    binding = verify_frozen_evidence_binding(
        tampered,
        rows,
        query=query,
    )

    assert binding["valid"] is False
    assert "manifest_fingerprint_mismatch" in binding["issues"]
    assert "request_query_fingerprint_mismatch" in binding["issues"]


def test_layer78_coverage_receipt_from_wrong_query_is_rejected_by_repair_gate():
    query = "Deep recall my recovery timeline"
    manifest, rows, _version = manifest_for(query)
    expected = verify_frozen_evidence_binding(
        manifest,
        rows,
        query=query,
    )
    wrong = dict(expected)
    wrong["request_query_sha256"] = sha256(b"different query").hexdigest()

    reply, final = choose_publication_repair(
        "first",
        audit("partial", 0),
        "repair",
        audit("citation_checks_passed", 2),
        first_coverage=simple_coverage(expected),
        repaired_coverage=simple_coverage(wrong),
        frozen_binding=expected,
    )

    assert reply == "first"
    assert final["repair_accepted"] is False
    assert final["repair_rejection_reason"] == "repair_receipt_mismatch"
    assert (
        "coverage_query_binding_mismatch"
        in final["repair_candidate_receipt_integrity"]["issues"]
    )


def test_layer78_layer77_verification_without_query_remains_usable_downstream():
    query = "Deep recall my recovery timeline"
    manifest, rows, _version = manifest_for(query)

    binding = verify_frozen_evidence_binding(manifest, rows)

    assert binding["valid"] is True
    assert binding["query_bound"] is True
    assert binding["query_verified"] is False
    assert binding["actual_request_query_sha256"] == ""


def test_layer78_pre_v5_bound_manifest_without_query_hash_remains_compatible():
    query = "Deep recall my recovery timeline"
    manifest, rows, _version = manifest_for(query)
    legacy_v4 = dict(manifest)
    legacy_v4.pop("manifest_sha256")
    legacy_v4.pop("query_sha256")
    from core.cognition.publication_repair import composition_manifest_sha256
    legacy_v4["manifest_sha256"] = composition_manifest_sha256(legacy_v4)

    binding = verify_frozen_evidence_binding(
        legacy_v4,
        rows,
        query=query,
    )

    assert binding["valid"] is True
    assert binding["query_bound"] is False
    assert binding["query_verified"] is False


def test_layer78_live_server_verifies_current_user_message_against_frozen_contract():
    source = (Path(__file__).resolve().parents[1] / "api" / "server.py").read_text(
        encoding="utf-8"
    )

    assert "query=user_message" in source
    assert '"deep_recall_query_binding_mismatch"' in source
    assert "does not match your current" in source
