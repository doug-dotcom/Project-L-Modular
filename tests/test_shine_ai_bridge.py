import httpx
import pytest

from core.cognition.model_independence import build_model_request, invoke_model
from core.cognition.model_routing import configured_adapter
from core.cognition.shine_ai_bridge import ShineAIBridgeError, ShineAIModelAdapter


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "request_id": "shine-ai-request-1",
            "status": "ok",
            "answer": '{"fact":"Supported [[l-evidence-1]]"}',
            "route": "model",
            "provider": "openai",
            "model": "gpt-6-sol",
            "model_tier": "deep",
            "reasoning_effort": "high",
            "reason": "Deep route.",
            "delivery": {"mode": "normal", "reason": "L verifies downstream."},
            "verification": {"mode": "not-needed"},
            "efficiency": {
                "input_tokens": 100,
                "output_tokens": 30,
                "total_tokens": 130,
                "cached_input_tokens": 0,
                "estimated_cost_usd": 0.01,
            },
        }


class Fallback:
    provider = "fallback"
    model_id = "fallback-model"
    available = True

    def __init__(self):
        self.calls = []

    def generate(self, request):
        self.calls.append(request)
        return {
            "status": "complete",
            "content": "fallback output",
            "provider": self.provider,
            "model_id": self.model_id,
            "receipt": {},
        }


def bridge(**kwargs):
    return ShineAIModelAdapter(
        base_url="https://shine-ai.example",
        app_id="shine-companion",
        key_id="l-runtime-test",
        secret="test-credential-material-" * 2,
        **kwargs,
    )


def test_bridge_preserves_governed_messages_json_mode_and_l_markers():
    seen = {}

    def post(url, *, content, headers, timeout, follow_redirects):
        seen["url"] = url
        seen["content"] = content
        seen["headers"] = headers
        return FakeResponse()

    request = build_model_request(
        [
            {"role": "system", "content": "You are L. Preserve the evidence contract."},
            {"role": "user", "content": "Use the frozen packet."},
        ],
        purpose="l_deep_recall_publication_repair",
        routing_purpose="l_recall_response",
        response_format={"type": "json_object"},
    )
    result = invoke_model(
        bridge(
            post_impl=post,
            now=lambda: 1_700_000_000,
            nonce_factory=lambda: "nonce-1234567890abcd",
        ),
        request,
    )

    body_text = seen["content"].decode("utf-8")
    assert '"app":"shine-companion"' in body_text
    assert '"trusted_output_mode":"json_object"' in body_text
    assert '"tier":"deep"' in body_text
    assert '"max_output_tokens":8192' in body_text
    assert '"allow_response_cache":false' in body_text
    assert "You are L. Preserve the evidence contract." in body_text
    assert "X-Shine-Signature" in seen["headers"]
    assert result["content"] == '{"fact":"Supported [[l-evidence-1]]"}'
    assert result["provider"] == "shine-ai"


def test_text_network_failure_never_uses_local_fallback():
    fallback = Fallback()

    def post(*args, **kwargs):
        raise httpx.ConnectError("offline")

    request = build_model_request(
        [{"role": "user", "content": "Hello"}],
        purpose="l_conversation_response",
    )
    with pytest.raises(ShineAIBridgeError, match="shine_ai_unavailable"):
        bridge(fallback=fallback, post_impl=post).generate(request)
    assert fallback.calls == []


def test_multimodal_request_uses_explicit_local_fallback_only():
    fallback = Fallback()
    request = build_model_request(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is this?"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,AAAA"},
                    },
                ],
            }
        ],
        purpose="l_image_understanding",
    )
    result = bridge(
        fallback=fallback,
        post_impl=lambda *args, **kwargs: pytest.fail("unexpected Shine-AI call"),
    ).generate(request)

    assert result["content"] == "fallback output"
    assert result["receipt"]["shine_ai_bridge"]["status"] == "explicit_local_fallback"
    assert result["receipt"]["shine_ai_bridge"]["network_failure_fallback"] is False
    assert len(fallback.calls) == 1


def test_partial_bridge_configuration_fails_closed():
    adapter = configured_adapter(
        None,
        "gpt-4o-mini",
        {
            "SHINE_AI_URL": "https://shine-ai.example",
            "SHINE_AI_APP_ID": "shine-companion",
        },
    )
    assert adapter.available is False
    assert adapter.model_id == "shine-ai-bridge-misconfigured"
