from pathlib import Path

import pytest

from core.cognition.model_independence import (
    build_model_request,
    invoke_model,
)
from core.cognition.publication_repair import (
    build_deep_recall_prompt_binding,
    choose_publication_repair,
    publication_receipt_integrity,
)


def frozen_binding():
    return {
        "status": "verified",
        "valid": True,
        "actual_manifest_sha256": "a" * 64,
        "actual_evidence_packet_sha256": "b" * 64,
        "request_query_sha256": "c" * 64,
    }


def prompt_parts():
    evidence = 'MEMORY ANSWER CONTRACT\nEVIDENCE ARRAY: [{"source":"raw_catchall:1"}]'
    coverage = 'DEEP RECALL COVERAGE RECEIPT — represented parts: ["timeline"]'
    system = "BASE SYSTEM\n" + evidence + "\n" + coverage
    return system, evidence, coverage


def valid_prompt_binding():
    system, evidence, coverage = prompt_parts()
    return build_deep_recall_prompt_binding(
        system,
        evidence,
        coverage,
        frozen_binding(),
    )


class Adapter:
    available = True
    provider = "fixture"
    model_id = "fixture-model"

    def __init__(self, mutate=False):
        self.mutate = mutate
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.mutate and isinstance(request.get("context_binding"), dict):
            request["context_binding"]["status"] = "tampered_after_verify"
        return {
            "status": "complete",
            "content": "generated",
        }


def generation(binding, purpose):
    transport = {
        "version": "1.0",
        "integrity": "verified",
        "api": "responses",
        "model_id": "fixture-model",
        "request_sha256": "d" * 64,
        "payload_sha256": "f" * 64,
        "issues": [],
    }
    from core.cognition.publication_repair import _canonical_sha256
    transport["receipt_sha256"] = _canonical_sha256(transport)
    response = {
        "version": "1.0",
        "integrity": "verified",
        "api": "responses",
        "response_id": "resp_fixture",
        "requested_model": "fixture-model",
        "returned_model": "fixture-model",
        "status": "complete",
        "request_sha256": "d" * 64,
        "transport_receipt_sha256": transport["receipt_sha256"],
        "content_sha256": "e" * 64,
        "issues": [],
    }
    response["receipt_sha256"] = _canonical_sha256(response)
    return {
        "request_sha256": "d" * 64,
        "content_sha256": "e" * 64,
        "purpose": purpose,
        "model_id": "fixture-model",
        "request_integrity": "verified",
        "context_binding": dict(binding),
        "provider_transport": transport,
        "provider_response": response,
    }


def coverage(binding=None):
    return {
        "status": "complete",
        "complete": True,
        "covered_count": 1,
        "missing_count": 0,
        "frozen_evidence_binding": binding or frozen_binding(),
    }


def audit(status, citations, gen):
    return {
        "status": status,
        "blocks_checked": 1,
        "blocks_withheld": 1 if status == "partial" else 0,
        "citations_checked": citations,
        "checks": [],
        "generation": gen,
    }


def test_layer81_exact_prompt_composition_produces_verified_binding():
    system, evidence, coverage_text = prompt_parts()
    binding = build_deep_recall_prompt_binding(
        system,
        evidence,
        coverage_text,
        frozen_binding(),
    )

    assert binding["valid"] is True
    assert binding["status"] == "verified"
    assert len(binding["system_prompt_sha256"]) == 64
    assert len(binding["evidence_contract_sha256"]) == 64
    assert len(binding["coverage_contract_sha256"]) == 64
    assert len(binding["binding_sha256"]) == 64
    assert binding["manifest_sha256"] == "a" * 64
    assert binding["evidence_packet_sha256"] == "b" * 64
    assert binding["query_sha256"] == "c" * 64


@pytest.mark.parametrize(
    "system_transform,expected_issue",
    [
        (
            lambda system, evidence, coverage: system.replace(evidence, ""),
            "evidence_contract_not_exactly_once",
        ),
        (
            lambda system, evidence, coverage: system + "\n" + evidence,
            "evidence_contract_not_exactly_once",
        ),
        (
            lambda system, evidence, coverage: system.replace(coverage, ""),
            "coverage_contract_not_exactly_once",
        ),
    ],
)
def test_layer81_missing_or_duplicate_prompt_components_fail_closed(
    system_transform,
    expected_issue,
):
    system, evidence, coverage_text = prompt_parts()
    binding = build_deep_recall_prompt_binding(
        system_transform(system, evidence, coverage_text),
        evidence,
        coverage_text,
        frozen_binding(),
    )

    assert binding["valid"] is False
    assert binding["status"] == "mismatch"
    assert expected_issue in binding["issues"]


def test_layer81_invalid_frozen_binding_cannot_earn_prompt_verification():
    system, evidence, coverage_text = prompt_parts()
    frozen = frozen_binding()
    frozen["valid"] = False

    binding = build_deep_recall_prompt_binding(
        system,
        evidence,
        coverage_text,
        frozen,
    )

    assert binding["valid"] is False
    assert "frozen_binding_invalid" in binding["issues"]


def test_layer81_context_binding_is_inside_layer80_request_hash():
    binding = valid_prompt_binding()
    first = build_model_request(
        [{"role": "system", "content": "x"}, {"role": "user", "content": "y"}],
        purpose="l_user_response",
        context_binding=binding,
    )
    changed = dict(binding)
    changed["system_prompt_sha256"] = "f" * 64
    second = build_model_request(
        [{"role": "system", "content": "x"}, {"role": "user", "content": "y"}],
        purpose="l_user_response",
        context_binding=changed,
    )

    assert first["context_binding"] == binding
    assert first["request_sha256"] != second["request_sha256"]


def test_layer81_context_binding_must_be_object():
    with pytest.raises(TypeError, match="model_context_binding_must_be_object"):
        build_model_request(
            [{"role": "user", "content": "hello"}],
            purpose="test",
            context_binding="not-a-dict",
        )


def test_layer81_adapter_cannot_mutate_verified_binding_receipt_after_hash_check():
    binding = valid_prompt_binding()
    request = build_model_request(
        [{"role": "user", "content": "hello"}],
        purpose="l_user_response",
        context_binding=binding,
    )
    result = invoke_model(Adapter(mutate=True), request)

    assert request["context_binding"]["status"] == "tampered_after_verify"
    assert result["context_binding"]["status"] == "verified"
    assert result["receipt"]["context_binding"]["status"] == "verified"
    assert result["context_binding"]["binding_sha256"] == binding["binding_sha256"]


def test_layer81_publication_rejects_missing_generation_prompt_binding():
    binding = valid_prompt_binding()
    gen = generation(binding, "l_user_response")
    gen.pop("context_binding")

    receipt = publication_receipt_integrity(
        "reply",
        {"generation": gen},
        coverage(),
        expected_frozen_binding=frozen_binding(),
        expected_generation_purpose="l_user_response",
        expected_prompt_binding=binding,
    )

    assert receipt["valid"] is False
    assert "generation_prompt_binding_missing" in receipt["issues"]


def test_layer81_publication_rejects_tampered_prompt_binding_receipt():
    binding = valid_prompt_binding()
    tampered = dict(binding)
    tampered["system_prompt_sha256"] = "f" * 64
    gen = generation(tampered, "l_user_response")

    receipt = publication_receipt_integrity(
        "reply",
        {"generation": gen},
        coverage(),
        expected_frozen_binding=frozen_binding(),
        expected_generation_purpose="l_user_response",
        expected_prompt_binding=binding,
    )

    assert receipt["valid"] is False
    assert "generation_prompt_binding_receipt_invalid" in receipt["issues"]
    assert "generation_prompt_binding_mismatch" not in receipt["issues"]


def test_layer81_repair_selector_rejects_prompt_binding_from_another_context():
    expected = valid_prompt_binding()
    other = dict(expected)
    other["query_sha256"] = "9" * 64
    other_payload = dict(other)
    other_payload.pop("binding_sha256", None)
    from core.cognition.publication_repair import _canonical_sha256
    other["binding_sha256"] = _canonical_sha256(other_payload)

    first = audit(
        "partial",
        0,
        generation(expected, "l_user_response"),
    )
    repaired = audit(
        "citation_checks_passed",
        2,
        generation(other, "l_deep_recall_publication_repair"),
    )

    reply, final = choose_publication_repair(
        "first",
        first,
        "repair",
        repaired,
        first_coverage=coverage(),
        repaired_coverage=coverage(),
        frozen_binding=frozen_binding(),
        prompt_binding=expected,
    )

    assert reply == "first"
    assert final["repair_accepted"] is False
    assert final["repair_rejection_reason"] == "repair_receipt_mismatch"
    assert (
        "generation_prompt_binding_mismatch"
        in final["repair_candidate_receipt_integrity"]["issues"]
    )


def test_layer81_live_server_builds_once_and_reuses_same_prompt_binding_for_repair():
    source = (Path(__file__).resolve().parents[1] / "api" / "server.py").read_text(
        encoding="utf-8"
    )

    assert "evidence_contract_text = evidence_prompt(evidence_rows_for_prompt)" in source
    assert "coverage_contract_text = coverage_contract(composition_manifest)" in source
    assert "deep_recall_prompt_binding = build_deep_recall_prompt_binding(" in source
    assert '"reason": "deep_recall_prompt_binding_mismatch"' in source
    assert source.count("context_binding=deep_recall_prompt_binding") >= 2
    assert "prompt_binding=deep_recall_prompt_binding" in source


def test_layer81_evaluation_manifest_exposes_prompt_composition_binding():
    source = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "cognition"
        / "evidence_evaluation.py"
    ).read_text(encoding="utf-8")

    assert '"deep_recall_prompt_composition_binding"' in source
