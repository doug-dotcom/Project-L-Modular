import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace as NS

from core.cognition.model_independence import (
    OpenAIChatCompletionsAdapter,
    OpenAIResponsesAdapter,
    build_model_request,
    invoke_model,
    provider_payload_sha256,
    provider_transport_receipt,
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
    evidence = "MEMORY ANSWER CONTRACT\nPRIVATE EVIDENCE TEXT"
    coverage = "DEEP RECALL COVERAGE RECEIPT\nPRIVATE COVERAGE TEXT"
    system = "BASE SYSTEM\n" + evidence + "\n" + coverage
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


def generation_without_transport():
    return {
        "request_sha256": "d" * 64,
        "content_sha256": "e" * 64,
        "purpose": "l_user_response",
        "model_id": "gpt-6-astra",
        "request_integrity": "verified",
        "context_binding": prompt_binding(),
    }


def valid_transport(*, request_hash="d" * 64, model_id="gpt-6-astra"):
    receipt = {
        "version": "1.0",
        "integrity": "verified",
        "api": "responses",
        "model_id": model_id,
        "request_sha256": request_hash,
        "payload_sha256": "f" * 64,
        "issues": [],
    }
    receipt["receipt_sha256"] = canonical(receipt)
    return receipt


def valid_provider_response(
    transport,
    *,
    requested_model="gpt-6-astra",
    returned_model="gpt-6-astra",
    request_hash="d" * 64,
    content_hash="e" * 64,
):
    receipt = {
        "version": "1.0",
        "integrity": "verified",
        "api": "responses",
        "response_id": "resp_fixture",
        "requested_model": requested_model,
        "returned_model": returned_model,
        "status": "complete",
        "request_sha256": request_hash,
        "transport_receipt_sha256": transport["receipt_sha256"],
        "content_sha256": content_hash,
        "issues": [],
    }
    receipt["receipt_sha256"] = canonical(receipt)
    return receipt


def test_layer82_chat_transport_receipt_hashes_exact_sdk_payload():
    seen = {}

    def create(**options):
        seen.update(options)
        return NS(
            choices=[
                NS(
                    finish_reason="stop",
                    message=NS(content="done", refusal=None),
                )
            ],
            model="gpt-4o-mini",
            usage=None,
        )

    client = NS(chat=NS(completions=NS(create=create)))
    request = build_model_request(
        [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Question"},
        ],
        purpose="test",
        temperature=0.4,
        max_output_tokens=333,
        response_format={"type": "json_object"},
    )
    result = invoke_model(
        OpenAIChatCompletionsAdapter(client, "gpt-4o-mini"),
        request,
    )
    transport = result["receipt"]["provider_transport"]

    assert transport["integrity"] == "verified"
    assert transport["api"] == "chat_completions"
    assert transport["request_sha256"] == request["request_sha256"]
    assert transport["payload_sha256"] == provider_payload_sha256(seen)
    assert transport["receipt_sha256"] == canonical(
        {k: v for k, v in transport.items() if k != "receipt_sha256"}
    )
    assert seen["messages"] == request["messages"]
    assert seen["temperature"] == 0.4
    assert seen["max_tokens"] == 333
    assert seen["store"] is False


def test_layer82_responses_transport_receipt_hashes_exact_sdk_payload():
    seen = {}

    def create(**options):
        seen.update(options)
        return NS(
            status="completed",
            output_text="done",
            output=[],
            model="gpt-6-astra",
            usage=None,
            id="resp_test",
            service_tier="default",
        )

    client = NS(responses=NS(create=create))
    request = build_model_request(
        [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Question"},
        ],
        purpose="test",
        max_output_tokens=4096,
        response_format={"type": "json_object"},
    )
    result = invoke_model(
        OpenAIResponsesAdapter(client, "gpt-6-astra", reasoning_effort="low"),
        request,
    )
    transport = result["receipt"]["provider_transport"]

    assert transport["integrity"] == "verified"
    assert transport["api"] == "responses"
    assert transport["request_sha256"] == request["request_sha256"]
    assert transport["payload_sha256"] == provider_payload_sha256(seen)
    assert seen["input"] == request["messages"]
    assert seen["reasoning"] == {"effort": "low"}
    assert seen["text"] == {"format": {"type": "json_object"}}
    assert seen["max_output_tokens"] == 4096
    assert seen["store"] is False


def test_layer82_transport_validator_detects_message_translation_mismatch():
    request = build_model_request(
        [{"role": "user", "content": "Original"}],
        purpose="test",
        temperature=0.2,
    )
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Changed"}],
        "store": False,
        "temperature": 0.2,
    }

    receipt = provider_transport_receipt(
        request,
        payload,
        api="chat_completions",
        model_id="gpt-4o-mini",
    )

    assert receipt["integrity"] == "mismatch"
    assert "provider_messages_mismatch" in receipt["issues"]


def test_layer82_transport_validator_detects_responses_input_drop():
    request = build_model_request(
        [
            {"role": "system", "content": "Evidence contract"},
            {"role": "user", "content": "Question"},
        ],
        purpose="test",
    )
    payload = {
        "model": "gpt-6-astra",
        "input": [{"role": "user", "content": "Question"}],
        "store": False,
        "max_output_tokens": 8192,
        "reasoning": {"effort": "low"},
    }

    receipt = provider_transport_receipt(
        request,
        payload,
        api="responses",
        model_id="gpt-6-astra",
        reasoning_effort="low",
    )

    assert receipt["integrity"] == "mismatch"
    assert "provider_input_mismatch" in receipt["issues"]


def test_layer82_transport_receipt_contains_no_prompt_or_evidence_text():
    secret = "VERY PRIVATE DEEP RECALL EVIDENCE"
    request = build_model_request(
        [
            {"role": "system", "content": secret},
            {"role": "user", "content": "Question"},
        ],
        purpose="test",
        temperature=0.3,
    )
    payload = {
        "model": "gpt-4o-mini",
        "messages": request["messages"],
        "store": False,
        "temperature": 0.3,
    }
    receipt = provider_transport_receipt(
        request,
        payload,
        api="chat_completions",
        model_id="gpt-4o-mini",
    )
    encoded = json.dumps(receipt)

    assert secret not in encoded
    assert "messages" not in receipt
    assert "input" not in receipt
    assert set(receipt) == {
        "version",
        "integrity",
        "api",
        "model_id",
        "request_sha256",
        "payload_sha256",
        "issues",
        "receipt_sha256",
    }


def test_layer82_publication_rejects_missing_provider_transport():
    binding = prompt_binding()
    receipt = publication_receipt_integrity(
        "reply",
        {"generation": generation_without_transport()},
        coverage(),
        expected_frozen_binding=frozen_binding(),
        expected_generation_purpose="l_user_response",
        expected_prompt_binding=binding,
    )

    assert receipt["valid"] is False
    assert "generation_provider_transport_missing" in receipt["issues"]


def test_layer82_publication_rejects_tampered_transport_receipt():
    generation = generation_without_transport()
    transport = valid_transport()
    transport["payload_sha256"] = "9" * 64
    generation["provider_transport"] = transport

    receipt = publication_receipt_integrity(
        "reply",
        {"generation": generation},
        coverage(),
        expected_frozen_binding=frozen_binding(),
        expected_generation_purpose="l_user_response",
        expected_prompt_binding=prompt_binding(),
    )

    assert receipt["valid"] is False
    assert "generation_provider_transport_receipt_invalid" in receipt["issues"]


def test_layer82_publication_rejects_transport_from_different_request():
    generation = generation_without_transport()
    generation["provider_transport"] = valid_transport(request_hash="8" * 64)

    receipt = publication_receipt_integrity(
        "reply",
        {"generation": generation},
        coverage(),
        expected_frozen_binding=frozen_binding(),
        expected_generation_purpose="l_user_response",
        expected_prompt_binding=prompt_binding(),
    )

    assert receipt["valid"] is False
    assert "generation_provider_transport_request_mismatch" in receipt["issues"]


def test_layer82_publication_rejects_transport_model_mismatch():
    generation = generation_without_transport()
    transport = valid_transport(model_id="gpt-5.6-sol")
    generation["provider_transport"] = transport
    generation["provider_response"] = valid_provider_response(
        transport,
        requested_model="gpt-6-astra",
        returned_model="gpt-6-astra",
    )

    receipt = publication_receipt_integrity(
        "reply",
        {"generation": generation},
        coverage(),
        expected_frozen_binding=frozen_binding(),
        expected_generation_purpose="l_user_response",
        expected_prompt_binding=prompt_binding(),
    )

    assert receipt["valid"] is False
    assert (
        "generation_provider_response_requested_model_mismatch"
        in receipt["issues"]
    )


def test_layer82_nested_invoke_preserves_transport_receipt():
    transport = valid_transport()

    class Inner:
        available = True
        provider = "fixture"
        model_id = "fixture-model"

        def generate(self, request):
            return {
                "status": "complete",
                "content": "done",
                "receipt": {"provider_transport": dict(transport)},
            }

    request = build_model_request(
        [{"role": "user", "content": "Hello"}],
        purpose="test",
    )
    result = invoke_model(Inner(), request)

    assert result["receipt"]["provider_transport"] == transport


def test_layer82_live_server_carries_transport_for_first_and_repair_generation():
    source = (Path(__file__).resolve().parents[1] / "api" / "server.py").read_text(
        encoding="utf-8"
    )

    assert source.count('"provider_transport": dict(') >= 2
    assert '(result.get("receipt") or {}).get("provider_transport")' in source
    assert '(repair_result.get("receipt") or {}).get(' in source


def test_layer82_evaluation_manifest_exposes_provider_transport_binding():
    source = (
        Path(__file__).resolve().parents[1]
        / "core"
        / "cognition"
        / "evidence_evaluation.py"
    ).read_text(encoding="utf-8")

    assert 'VERSION = "2.3"' in source
    assert '"provider_transport_payload_binding"' in source
