from hashlib import sha256
from pathlib import Path

import pytest

from core.cognition.model_independence import (
    build_model_request,
    invoke_model,
    model_request_sha256,
)
from core.cognition.publication_repair import (
    choose_publication_repair,
    publication_receipt_integrity,
)


class FixtureAdapter:
    available = True
    provider = "fixture"
    model_id = "fixture-model"

    def __init__(self, content="fixture output", receipt=None):
        self.content = content
        self.receipt = receipt
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        result = {
            "status": "complete",
            "content": self.content,
        }
        if self.receipt is not None:
            result["receipt"] = dict(self.receipt)
        return result


def h(text):
    return sha256(text.encode("utf-8")).hexdigest()


def support_for(raw, status="passed"):
    return {
        "status": status,
        "draft_sha256": h(raw),
        "failed_blocks": [],
        "conflict_blocks": [],
        "compound_blocks": [],
    }


def generation_for(raw, purpose, integrity="verified", request_hash=None):
    return {
        "request_sha256": request_hash or ("a" * 64),
        "content_sha256": h(raw),
        "purpose": purpose,
        "model_id": "fixture-model",
        "request_integrity": integrity,
    }


def frozen_binding():
    return {
        "status": "verified",
        "valid": True,
        "actual_manifest_sha256": "b" * 64,
        "actual_evidence_packet_sha256": "c" * 64,
        "request_query_sha256": "d" * 64,
    }


def coverage(binding=None):
    return {
        "status": "complete",
        "complete": True,
        "covered_count": 1,
        "missing_count": 0,
        "frozen_evidence_binding": binding or frozen_binding(),
    }


def audit(raw, *, status, citations, purpose, integrity="verified"):
    return {
        "status": status,
        "blocks_checked": 1,
        "blocks_withheld": 1 if status == "partial" else 0,
        "citations_checked": citations,
        "checks": [],
        "claim_support": support_for(raw),
        "generation": generation_for(raw, purpose, integrity=integrity),
    }


def test_layer80_build_request_hashes_exact_provider_neutral_payload():
    request = build_model_request(
        [
            {"role": "system", "content": "System contract"},
            {"role": "user", "content": "Deep recall this"},
        ],
        purpose="l_user_response",
        routing_purpose="l_recall_response",
        response_format={"type": "json_object"},
        temperature=0.45,
    )

    assert len(request["request_sha256"]) == 64
    assert request["request_sha256"] == model_request_sha256(request)

    same = build_model_request(
        [
            {"role": "system", "content": "System contract"},
            {"role": "user", "content": "Deep recall this"},
        ],
        purpose="l_user_response",
        routing_purpose="l_recall_response",
        response_format={"type": "json_object"},
        temperature=0.45,
    )
    assert same["request_sha256"] == request["request_sha256"]


def test_layer80_prompt_or_option_change_changes_request_fingerprint():
    first = build_model_request(
        [{"role": "user", "content": "Deep recall this"}],
        purpose="l_user_response",
        temperature=0.45,
    )
    changed_prompt = build_model_request(
        [{"role": "user", "content": "Deep recall that"}],
        purpose="l_user_response",
        temperature=0.45,
    )
    changed_option = build_model_request(
        [{"role": "user", "content": "Deep recall this"}],
        purpose="l_user_response",
        temperature=0.2,
    )

    assert first["request_sha256"] != changed_prompt["request_sha256"]
    assert first["request_sha256"] != changed_option["request_sha256"]


def test_layer80_mutated_request_is_rejected_before_adapter_invocation():
    request = build_model_request(
        [{"role": "user", "content": "Original"}],
        purpose="l_user_response",
    )
    request["messages"][0]["content"] = "Mutated after hashing"
    adapter = FixtureAdapter()

    with pytest.raises(ValueError, match="model_request_integrity_mismatch"):
        invoke_model(adapter, request)

    assert adapter.requests == []


def test_layer80_generation_receipt_binds_request_and_raw_output():
    request = build_model_request(
        [{"role": "user", "content": "Hello"}],
        purpose="l_user_response",
    )
    adapter = FixtureAdapter(content="raw generated answer")
    result = invoke_model(adapter, request)

    assert result["request_sha256"] == request["request_sha256"]
    assert result["content_sha256"] == h("raw generated answer")
    assert result["request_integrity"] == "verified"
    assert result["receipt"]["request_sha256"] == request["request_sha256"]
    assert result["receipt"]["content_sha256"] == h("raw generated answer")
    assert result["receipt"]["request_integrity"] == "verified"


def test_layer80_local_hashes_override_untrusted_provider_receipt_hashes():
    request = build_model_request(
        [{"role": "user", "content": "Hello"}],
        purpose="l_user_response",
    )
    adapter = FixtureAdapter(
        content="trusted local output",
        receipt={
            "request_sha256": "forged",
            "content_sha256": "forged",
            "request_integrity": "forged",
        },
    )
    result = invoke_model(adapter, request)

    assert result["receipt"]["request_sha256"] == request["request_sha256"]
    assert result["receipt"]["content_sha256"] == h("trusted local output")
    assert result["receipt"]["request_integrity"] == "verified"


def test_layer80_legacy_unhashed_request_is_marked_unbound_not_verified():
    request = {
        "interface_version": "1.0",
        "purpose": "legacy_fixture",
        "messages": [{"role": "user", "content": "Legacy"}],
        "temperature": 0.3,
    }
    result = invoke_model(FixtureAdapter(), request)

    assert result["request_integrity"] == "legacy_unbound"
    assert len(result["request_sha256"]) == 64


def test_layer80_publication_rejects_generation_output_not_matching_semantic_source_draft():
    raw = "raw model answer"
    audit_data = {
        "claim_support": support_for("different source draft"),
        "generation": generation_for(raw, "l_user_response"),
    }

    receipt = publication_receipt_integrity(
        "rendered",
        audit_data,
        coverage(frozen_binding()),
        expected_frozen_binding=frozen_binding(),
        expected_generation_purpose="l_user_response",
    )

    assert receipt["valid"] is False
    assert "generation_claim_support_draft_mismatch" in receipt["issues"]


def test_layer80_repair_selector_rejects_wrong_generation_purpose():
    binding = frozen_binding()
    first = audit(
        "first raw",
        status="partial",
        citations=0,
        purpose="l_user_response",
    )
    repaired = audit(
        "repair raw",
        status="citation_checks_passed",
        citations=2,
        purpose="l_user_response",
    )

    reply, final = choose_publication_repair(
        "first rendered",
        first,
        "repair rendered",
        repaired,
        first_coverage=coverage(binding),
        repaired_coverage=coverage(binding),
        frozen_binding=binding,
    )

    assert reply == "first rendered"
    assert final["repair_accepted"] is False
    assert final["repair_rejection_reason"] == "repair_receipt_mismatch"
    assert (
        "generation_purpose_mismatch"
        in final["repair_candidate_receipt_integrity"]["issues"]
    )


def test_layer80_repair_selector_rejects_unverified_live_generation():
    binding = frozen_binding()
    first = audit(
        "first raw",
        status="partial",
        citations=0,
        purpose="l_user_response",
    )
    repaired = audit(
        "repair raw",
        status="citation_checks_passed",
        citations=2,
        purpose="l_deep_recall_publication_repair",
        integrity="legacy_unbound",
    )

    reply, final = choose_publication_repair(
        "first rendered",
        first,
        "repair rendered",
        repaired,
        first_coverage=coverage(binding),
        repaired_coverage=coverage(binding),
        frozen_binding=binding,
    )

    assert reply == "first rendered"
    assert final["repair_rejection_reason"] == "repair_receipt_mismatch"
    assert (
        "generation_request_not_verified"
        in final["repair_candidate_receipt_integrity"]["issues"]
    )


def test_layer80_legacy_audits_without_generation_receipts_stay_compatible():
    first = {
        "status": "partial",
        "blocks_checked": 1,
        "blocks_withheld": 1,
        "citations_checked": 0,
        "checks": [],
    }
    repaired = {
        "status": "citation_checks_passed",
        "blocks_checked": 1,
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
            "covered_count": 0,
            "missing_count": 1,
        },
        repaired_coverage={
            "status": "complete",
            "complete": True,
            "covered_count": 1,
            "missing_count": 0,
        },
    )

    assert reply == "repair"
    assert final["repair_accepted"] is True


def test_layer80_live_server_attaches_first_and_repair_generation_receipts():
    source = (Path(__file__).resolve().parents[1] / "api" / "server.py").read_text(
        encoding="utf-8"
    )

    assert "first_generation_receipt = {" in source
    assert 'evidence_audit["generation"] = first_generation_receipt' in source
    assert "repair_generation_receipt = {" in source
    assert 'repaired_audit["generation"] = repair_generation_receipt' in source
    assert '"request_integrity": result.get("request_integrity")' in source
    assert '"request_integrity": repair_result.get("request_integrity")' in source


def test_layer80_evaluation_manifest_exposes_request_generation_binding():
    source = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "cognition"
        / "evidence_evaluation.py"
    ).read_text(encoding="utf-8")

    assert 'VERSION = "2.0"' in source
    assert '"model_request_generation_binding"' in source
