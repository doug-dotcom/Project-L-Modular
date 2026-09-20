import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from core.cognition.model_independence import (
    OpenAIChatCompletionsAdapter,
    OpenAIResponsesAdapter,
    build_model_request,
    invoke_model,
    provider_response_receipt,
)
from core.cognition.publication_repair import (
    build_deep_recall_prompt_binding,
    publication_receipt_integrity,
)


def canonical(value):
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def frozen_binding():
    return {
        "status": "verified",
        "valid": True,
        "actual_manifest_sha256": "a" * 64,
        "actual_evidence_packet_sha256": "b" * 64,
        "request_query_sha256": "c" * 64,
    }


def prompt_binding():
    evidence = "MEMORY ANSWER CONTRACT\nPRIVATE EVIDENCE"
    coverage = "DEEP RECALL COVERAGE RECEIPT\nPRIVATE COVERAGE"
    system = "BASE\n" + evidence + "\n" + coverage
    return build_deep_recall_prompt_binding(
        system,
        evidence,
        coverage,
        frozen_binding(),
    )


def coverage():
    return {
        "status": "complete",
        "complete": True,
        "covered_count": 1,
        "missing_count": 0,
        "frozen_evidence_binding": frozen_binding(),
    }


def transport(
    *,
    request_hash="d" * 64,
    model_id="gpt-6-astra",
    api="responses",
):
    receipt = {
        "version": "1.0",
        "integrity": "verified",
        "api": api,
        "model_id": model_id,
        "request_sha256": request_hash,
        "payload_sha256": "f" * 64,
        "issues": [],
    }
    receipt["receipt_sha256"] = canonical(receipt)
    return receipt


def response_receipt(
    transport_receipt,
    *,
    request_hash="d" * 64,
    content_hash="e" * 64,
    requested_model="gpt-6-astra",
    returned_model="gpt-6-astra",
    api="responses",
    status="complete",
):
    receipt = {
        "version": "1.0",
        "integrity": "verified",
        "api": api,
        "response_id": "resp_fixture",
        "requested_model": requested_model,
        "returned_model": returned_model,
        "status": status,
        "request_sha256": request_hash,
        "transport_receipt_sha256": transport_receipt["receipt_sha256"],
        "content_sha256": content_hash,
        "issues": [],
    }
    receipt["receipt_sha256"] = canonical(receipt)
    return receipt


def generation(
    *,
    model_id="gpt-6-astra",
    requested_model="gpt-6-astra",
    returned_model="gpt-6-astra",
):
    transport_receipt = transport(model_id=requested_model)
    provider_response = response_receipt(
        transport_receipt,
        requested_model=requested_model,
        returned_model=returned_model,
    )
    return {
        "request_sha256": "d" * 64,
        "content_sha256": "e" * 64,
        "purpose": "l_user_response",
        "model_id": model_id,
        "request_integrity": "verified",
        "context_binding": prompt_binding(),
        "provider_transport": transport_receipt,
        "provider_response": provider_response,
    }


def test_layer83_chat_adapter_binds_exact_provider_response_content():
    def create(**_options):
        return NS(
            id="chatcmpl_test",
            choices=[
                NS(
                    finish_reason="stop",
                    message=NS(content="provider text", refusal=None),
                )
            ],
            model="gpt-4o-mini-2026-08-01",
            usage=None,
        )

    client = NS(chat=NS(completions=NS(create=create)))
    request = build_model_request(
        [{"role": "user", "content": "hello"}],
        purpose="test",
    )
    result = invoke_model(
        OpenAIChatCompletionsAdapter(client, "gpt-4o-mini"),
        request,
    )
    receipt = result["receipt"]["provider_response"]

    assert receipt["integrity"] == "verified"
    assert receipt["api"] == "chat_completions"
    assert receipt["response_id"] == "chatcmpl_test"
    assert receipt["requested_model"] == "gpt-4o-mini"
    assert receipt["returned_model"] == "gpt-4o-mini-2026-08-01"
    assert receipt["content_sha256"] == sha256(
        b"provider text"
    ).hexdigest()
    assert (
        receipt["transport_receipt_sha256"]
        == result["receipt"]["provider_transport"]["receipt_sha256"]
    )
    assert result["model_id"] == "gpt-4o-mini-2026-08-01"


def test_layer83_responses_adapter_binds_exact_provider_response_content():
    def create(**_options):
        return NS(
            id="resp_test",
            status="completed",
            output_text="provider response text",
            output=[],
            model="gpt-6-astra-2026-09-01",
            usage=None,
            service_tier="default",
        )

    client = NS(responses=NS(create=create))
    request = build_model_request(
        [{"role": "user", "content": "hello"}],
        purpose="test",
    )
    result = invoke_model(
        OpenAIResponsesAdapter(client, "gpt-6-astra", reasoning_effort="low"),
        request,
    )
    receipt = result["receipt"]["provider_response"]

    assert receipt["integrity"] == "verified"
    assert receipt["api"] == "responses"
    assert receipt["response_id"] == "resp_test"
    assert receipt["requested_model"] == "gpt-6-astra"
    assert receipt["returned_model"] == "gpt-6-astra-2026-09-01"
    assert receipt["content_sha256"] == sha256(
        b"provider response text"
    ).hexdigest()
    assert result["content_sha256"] == receipt["content_sha256"]


def test_layer83_provider_response_receipt_contains_no_response_text():
    secret = "PRIVATE PROVIDER RESPONSE CONTENT"
    tr = transport()

    receipt = provider_response_receipt(
        NS(id="resp_secret", model="gpt-6-astra"),
        secret,
        status="complete",
        api="responses",
        requested_model="gpt-6-astra",
        request_sha256="d" * 64,
        transport_receipt=tr,
    )
    encoded = json.dumps(receipt)

    assert secret not in encoded
    assert "content" not in receipt
    assert receipt["content_sha256"] == sha256(secret.encode()).hexdigest()


def test_layer83_provider_response_detects_tampered_transport_receipt():
    tr = transport()
    tr["payload_sha256"] = "9" * 64

    receipt = provider_response_receipt(
        NS(id="resp_test", model="gpt-6-astra"),
        "done",
        status="complete",
        api="responses",
        requested_model="gpt-6-astra",
        request_sha256="d" * 64,
        transport_receipt=tr,
    )

    assert receipt["integrity"] == "mismatch"
    assert "provider_transport_receipt_invalid" in receipt["issues"]


def test_layer83_outer_boundary_rejects_adapter_text_changed_after_provider_receipt():
    request = build_model_request(
        [{"role": "user", "content": "hello"}],
        purpose="test",
    )
    tr = transport(
        request_hash=request["request_sha256"],
        model_id="fixture-model",
    )
    resp = response_receipt(
        tr,
        request_hash=request["request_sha256"],
        content_hash=sha256(b"provider original").hexdigest(),
        requested_model="fixture-model",
        returned_model="fixture-model",
    )

    class Adapter:
        available = True
        provider = "fixture"
        model_id = "fixture-model"

        def generate(self, _request):
            return {
                "status": "complete",
                "content": "adapter altered",
                "model_id": "fixture-model",
                "receipt": {
                    "provider_transport": tr,
                    "provider_response": resp,
                },
            }

    with pytest.raises(ValueError, match="provider_response_integrity_mismatch"):
        invoke_model(Adapter(), request)


def test_layer83_outer_boundary_rejects_status_changed_after_provider_receipt():
    request = build_model_request(
        [{"role": "user", "content": "hello"}],
        purpose="test",
    )
    tr = transport(
        request_hash=request["request_sha256"],
        model_id="fixture-model",
    )
    resp = response_receipt(
        tr,
        request_hash=request["request_sha256"],
        content_hash=sha256(b"done").hexdigest(),
        requested_model="fixture-model",
        returned_model="fixture-model",
        status="complete",
    )

    class Adapter:
        available = True
        provider = "fixture"
        model_id = "fixture-model"

        def generate(self, _request):
            return {
                "status": "incomplete",
                "content": "done",
                "model_id": "fixture-model",
                "receipt": {
                    "provider_transport": tr,
                    "provider_response": resp,
                },
            }

    with pytest.raises(ValueError, match="provider_response_integrity_mismatch"):
        invoke_model(Adapter(), request)


def test_layer83_publication_rejects_missing_provider_response():
    gen = generation()
    gen.pop("provider_response")

    receipt = publication_receipt_integrity(
        "reply",
        {"generation": gen},
        coverage(),
        expected_frozen_binding=frozen_binding(),
        expected_generation_purpose="l_user_response",
        expected_prompt_binding=prompt_binding(),
    )

    assert receipt["valid"] is False
    assert "generation_provider_response_missing" in receipt["issues"]


def test_layer83_publication_rejects_tampered_response_receipt():
    gen = generation()
    gen["provider_response"]["content_sha256"] = "9" * 64

    receipt = publication_receipt_integrity(
        "reply",
        {"generation": gen},
        coverage(),
        expected_frozen_binding=frozen_binding(),
        expected_generation_purpose="l_user_response",
        expected_prompt_binding=prompt_binding(),
    )

    assert receipt["valid"] is False
    assert "generation_provider_response_receipt_invalid" in receipt["issues"]


def test_layer83_publication_rejects_provider_content_not_matching_generation():
    gen = generation()
    provider = dict(gen["provider_response"])
    provider["content_sha256"] = "9" * 64
    provider.pop("receipt_sha256")
    provider["receipt_sha256"] = canonical(provider)
    gen["provider_response"] = provider

    receipt = publication_receipt_integrity(
        "reply",
        {"generation": gen},
        coverage(),
        expected_frozen_binding=frozen_binding(),
        expected_generation_purpose="l_user_response",
        expected_prompt_binding=prompt_binding(),
    )

    assert receipt["valid"] is False
    assert "generation_provider_response_content_mismatch" in receipt["issues"]


def test_layer83_versioned_returned_model_is_valid_when_requested_alias_matches_transport():
    gen = generation(
        model_id="gpt-6-astra-2026-09-01",
        requested_model="gpt-6-astra",
        returned_model="gpt-6-astra-2026-09-01",
    )

    receipt = publication_receipt_integrity(
        "reply",
        {"generation": gen},
        coverage(),
        expected_frozen_binding=frozen_binding(),
        expected_generation_purpose="l_user_response",
        expected_prompt_binding=prompt_binding(),
    )

    assert receipt["valid"] is True
    assert receipt["issues"] == []


def test_layer83_live_server_carries_provider_response_for_first_and_repair():
    source = (Path(__file__).resolve().parents[1] / "api" / "server.py").read_text(
        encoding="utf-8"
    )

    assert source.count('"provider_response": dict(') >= 2
    assert '(result.get("receipt") or {}).get("provider_response")' in source
    assert '(repair_result.get("receipt") or {}).get(' in source


def test_layer83_evaluation_manifest_exposes_provider_response_binding():
    source = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "cognition"
        / "evidence_evaluation.py"
    ).read_text(encoding="utf-8")

    assert 'VERSION = "2.3"' in source
    assert '"provider_response_content_binding"' in source
