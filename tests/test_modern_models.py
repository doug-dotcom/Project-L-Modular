import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import httpx
from openai import OpenAI
import pytest

from core.cognition.model_independence import (
    ModelGenerationError, OpenAIResponsesAdapter, OpenAIChatCompletionsAdapter,
    build_model_request, create_model_adapter, invoke_model, model_capabilities,
)
from core.cognition.model_routing import MeasuredModelRouter, REQUIRED_CASES, eligible_report, configured_adapter


def request(**kwargs):
    return build_model_request([{"role": "user", "content": "Return JSON about a fictional test."}], purpose="test", **kwargs)


def client_with_response(payload, seen):
    def handle(req):
        seen.update(path=req.url.path, body=json.loads(req.content))
        return httpx.Response(200, json=payload)
    return OpenAI(api_key="test-only", http_client=httpx.Client(transport=httpx.MockTransport(handle)))


def response_payload(status="completed"):
    return {"id": "resp_test", "object": "response", "created_at": 1, "status": status,
            "model": "gpt-6-astra", "output": [{"type": "message", "id": "msg_test", "role": "assistant",
            "status": "completed", "content": [{"type": "output_text", "text": '{"answer":"done"}', "annotations": []}]}],
            "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150,
                      "input_tokens_details": {"cached_tokens": 20}, "output_tokens_details": {"reasoning_tokens": 30}}}


@pytest.mark.parametrize("model", ["gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-sol-2026-07-09"])
def test_real_sdk_responses_translation_and_usage(model):
    seen = {}
    client = client_with_response(response_payload(), seen)
    result = invoke_model(create_model_adapter(client, model), request(max_output_tokens=4096, response_format={"type": "json_object"}))
    assert seen["path"] == "/v1/responses"
    assert seen["body"]["model"] == model
    assert "temperature" not in seen["body"] and "max_tokens" not in seen["body"]
    assert seen["body"]["reasoning"] == {"effort": "low"}
    assert seen["body"]["text"] == {"format": {"type": "json_object"}}
    assert seen["body"]["store"] is False
    assert result["receipt"]["usage"]["reasoning_tokens"] == 30
    assert result["receipt"]["usage"]["cached_input_tokens"] == 20
    assert result["receipt"]["cost"]["status"] == ("not_priced" if model.endswith("2026-07-09") else "estimated_standard_text")


def test_image_and_strict_schema_use_responses_shapes():
    seen = {}
    client = client_with_response(response_payload(), seen)
    req = build_model_request([{"role": "user", "content": [
        {"type": "text", "text": "What is visible?"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA==", "detail": "low"}}]}],
        purpose="l_image_understanding", response_format={"type": "json_schema", "json_schema": {
            "name": "example", "strict": True, "schema": {"type": "object"}}})
    invoke_model(create_model_adapter(client, "gpt-6-astra"), req)
    assert seen["body"]["input"][0]["content"][1] == {"type": "input_image", "image_url": "data:image/png;base64,AA==", "detail": "low"}
    assert seen["body"]["text"]["format"] == {"type": "json_schema", "name": "example", "strict": True, "schema": {"type": "object"}}


@pytest.mark.parametrize("status", ["incomplete", "failed", "cancelled", "in_progress"])
def test_partial_output_cannot_be_returned_as_completed(status):
    with pytest.raises(ModelGenerationError) as exc:
        invoke_model(create_model_adapter(client_with_response(response_payload(status), {}), "gpt-6-astra"), request())
    assert exc.value.receipt["status"] == status
    assert "answer" not in str(exc.value)


def test_refusal_and_unhandled_tool_output_are_not_success():
    for output in ([{"type": "message", "content": [{"type": "refusal", "refusal": "refused"}]}],
                   [{"type": "function_call", "name": "unexpected", "arguments": "{}"}]):
        response = NS(status="completed", output_text="partial", output=output)
        client = NS(responses=NS(create=lambda **_: response))
        with pytest.raises(ModelGenerationError):
            invoke_model(OpenAIResponsesAdapter(client, "gpt-6-astra"), request())


def test_chat_compatibility_omits_unsupported_parameters():
    seen = {}
    def generate(**options):
        seen.update(options)
        return NS(choices=[NS(finish_reason="stop", message=NS(content="done"))])
    client = NS(chat=NS(completions=NS(create=generate)))
    invoke_model(OpenAIChatCompletionsAdapter(client, "gpt-6-astra"), request(max_output_tokens=1000))
    assert "temperature" not in seen and "max_tokens" not in seen
    assert seen["max_completion_tokens"] == 1000
    assert model_capabilities("gpt-6-astra")["tools"] is False
    with pytest.raises(ValueError, match="reasoning_effort"):
        OpenAIResponsesAdapter(client, "gpt-6-astra", reasoning_effort="none")


def passing_report():
    return {"model_id": "gpt-5.6-terra", "api": "responses", "reasoning_effort": "low",
            "suite_version": "stage3-evidence-1", "mode": "model_with_synthetic_evidence",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "results": [{"case": case, "trial": trial, "passed": True, "duration_ms": 100,
                         "receipt": {"status": "complete", "requested_model": "gpt-5.6-terra", "api": "responses"}}
                        for case in REQUIRED_CASES for trial in (1, 2)]}


@pytest.mark.parametrize("failure", ["missing", "failed", "unfinished", "old", "naive_date", "duplicate", "slow"])
def test_unearned_route_is_rejected(failure):
    report = passing_report()
    if failure == "missing": report["results"].pop()
    if failure == "failed": report["results"][0]["passed"] = False
    if failure == "unfinished": report["results"][0]["receipt"]["status"] = "incomplete"
    if failure == "old": report["executed_at"] = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    if failure == "naive_date": report["executed_at"] = "2026-09-05T01:00:00"
    if failure == "duplicate": report["results"][0] = deepcopy(report["results"][1])
    if failure == "slow": report["results"][0]["duration_ms"] = 60001
    assert not eligible_report(report)


def test_router_uses_validated_recall_only_and_does_not_retry_failure(tmp_path):
    path = tmp_path / "routes.json"
    path.write_text(json.dumps({"enabled": True, "recall_evaluation": passing_report()}))
    router = MeasuredModelRouter(NS(), "gpt-4o-mini", routes_path=path)
    seen = []
    class Adapter:
        available = True
        provider = "test"
        model_id = "test"
        def generate(self, req):
            seen.append(req["routing_purpose"])
            return {"content": "done"}
    router.routes["l_recall_response"] = Adapter()
    assert invoke_model(router, request(routing_purpose="l_recall_response"))["receipt"]["routing"]["reason"] == "measured_recall_route"
    for purpose in ["rike_structured_reasoning", "l_report_response", "l_image_understanding", "l_conversation_response"]:
        with pytest.raises(AttributeError):
            invoke_model(router, request(routing_purpose=purpose))
    assert seen == ["l_recall_response"]


def test_default_router_finds_the_packaged_configuration():
    router = configured_adapter(NS(), "gpt-4o-mini", {})
    assert router.routing_manifest.get("configuration") != "missing_or_invalid"


def test_failed_generation_never_writes_assistant_memory(monkeypatch):
    from api import server
    saved = []
    class Adapter:
        available = True
        provider = "test"
        model_id = "test"
        def generate(self, req):
            return {"status": "incomplete", "content": "unfinished private output", "receipt": {"status": "incomplete"}}
    monkeypatch.setattr(server, "resolve_model_adapter", lambda: Adapter())
    monkeypatch.setattr(server, "build_rhee_packet", lambda _: {"context": "", "recall_active": False})
    monkeypatch.setattr(server, "route_capability", lambda _: {"handled": False, "status": "not_required"})
    monkeypatch.setattr(server, "run_cognitive_core", lambda *a, **kw: {})
    monkeypatch.setattr(server, "write_raw_catchall", lambda role, content, **kw: saved.append((role, content)))
    monkeypatch.setattr(server, "write_live_short_term", lambda *a: {"saved": True})
    monkeypatch.setattr(server, "run_brain_pipeline", lambda _: None)
    result = server.chat(server.ChatRequest(message="Hello L"))
    assert result["error"] is True
    assert result["model_receipt"]["status"] == "incomplete"
    assert all(role == "user" for role, content in saved)
    assert "unfinished" not in str(result)
