"""Project L Phase 11: provider-neutral foundation-model interface.

The adapter owns provider syntax. L's durable cognition, memory, identity and
governance receive and emit stable packets that survive a model replacement.
"""

from __future__ import annotations

from hashlib import sha256
import json
import re
from time import monotonic
from typing import Protocol


MODEL_INTERFACE_VERSION = "1.0"
ALLOWED_ROLES = {"system", "user", "assistant", "tool"}

PERSISTENT_SYSTEMS = (
    "metacognition",
    "rike_reasoning",
    "rhee_retrieval",
    "mary_longitudinal_intelligence",
    "quinn_governed_principles",
    "sara_memory_governance",
    "carol_evidence_hygiene",
    "specialist_services",
    "supabase_memory_and_cognitive_history",
)


class ModelAdapter(Protocol):
    provider: str
    model_id: str
    available: bool

    def generate(self, request: dict) -> dict:
        """Return the standard model-result contract."""


def build_model_request(
    messages: list[dict],
    *,
    purpose: str,
    temperature: float = 0.3,
    max_output_tokens: int | None = None,
    response_format: dict | None = None,
    routing_purpose: str | None = None,
) -> dict:
    """Build a provider-neutral request and reject malformed context early."""
    if not isinstance(messages, list) or not messages:
        raise ValueError("model_messages_required")
    clean_messages = []
    for raw in messages:
        if not isinstance(raw, dict):
            raise TypeError("model_message_must_be_object")
        role = str(raw.get("role") or "")
        if role not in ALLOWED_ROLES:
            raise ValueError("model_message_role_invalid")
        content = raw.get("content")
        if not isinstance(content, (str, list)):
            raise TypeError("model_message_content_invalid")
        clean_messages.append({"role": role, "content": content})
    request = {
        "interface_version": MODEL_INTERFACE_VERSION,
        "purpose": str(purpose or "general")[:100],
        "messages": clean_messages,
        "temperature": max(0.0, min(2.0, float(temperature))),
    }
    if max_output_tokens is not None:
        request["max_output_tokens"] = max(1, int(max_output_tokens))
    if response_format:
        request["response_format"] = dict(response_format)
    if routing_purpose:
        request["routing_purpose"] = str(routing_purpose)
    return request


def invoke_model(adapter: ModelAdapter, request: dict) -> dict:
    """Invoke any conforming adapter and enforce one stable result shape."""
    if adapter is None or not getattr(adapter, "available", False):
        raise RuntimeError("model_adapter_unavailable")
    if request.get("interface_version") != MODEL_INTERFACE_VERSION:
        raise ValueError("model_interface_version_mismatch")
    result = adapter.generate(request)
    if not isinstance(result, dict):
        raise TypeError("model_result_must_be_object")
    content = result.get("content")
    if not isinstance(content, str):
        raise TypeError("model_result_content_must_be_text")
    normalised = {
        "interface_version": MODEL_INTERFACE_VERSION,
        "status": str(result.get("status") or "complete"),
        "content": content,
        "provider": str(result.get("provider") or getattr(adapter, "provider", "unknown")),
        "model_id": str(result.get("model_id") or getattr(adapter, "model_id", "unknown")),
        "purpose": str(request.get("purpose") or "general"),
    }
    if isinstance(result.get("receipt"), dict):
        normalised["receipt"] = result["receipt"]
    if normalised["status"] != "complete" or not content.strip():
        raise ModelGenerationError(normalised.get("receipt", {}))
    return normalised


class ModelGenerationError(RuntimeError):
    """A provider returned no usable, completed answer; never promote it as memory."""

    def __init__(self, receipt):
        super().__init__("model_generation_not_complete")
        self.receipt = receipt


def model_capabilities(model_id: str) -> dict:
    modern = bool(re.match(r"^(?:gpt-[56](?:[.-]|$)|o[134](?:-|$))", model_id))
    astra = model_id.startswith("gpt-6")
    return {
        "api": "responses" if modern else "chat_completions",
        "reasoning": modern,
        "supports_temperature": not modern,
        "reasoning_efforts": (["low", "medium", "high", "xhigh", "max"] if astra else
                              ["none", "low", "medium", "high", "xhigh", "max"] if modern else []),
        "text": True,
        "images": model_id.startswith(("gpt-4o", "gpt-4.1", "gpt-5", "gpt-6")),
        "json_output": True,
        "tools": False,
        "audio": False,
        "video": False,
        "streaming": False,
    }


def _get(value, key, default=None):
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)


def model_receipt(response, *, model_id, api, status, started, effort=None) -> dict:
    usage = _get(response, "usage")
    input_tokens = _get(usage, "input_tokens", _get(usage, "prompt_tokens"))
    output_tokens = _get(usage, "output_tokens", _get(usage, "completion_tokens"))
    input_details = _get(usage, "input_tokens_details", _get(usage, "prompt_tokens_details"))
    output_details = _get(usage, "output_tokens_details", _get(usage, "completion_tokens_details"))
    return {
        "version": "1.0", "provider": "openai", "requested_model": model_id,
        "model_id": _get(response, "model") or model_id, "api": api,
        "response_id": _get(response, "id"), "status": status,
        "duration_ms": round((monotonic() - started) * 1000), "reasoning_effort": effort,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens,
                  "total_tokens": _get(usage, "total_tokens"),
                  "cached_input_tokens": _get(input_details, "cached_tokens"),
                  "reasoning_tokens": _get(output_details, "reasoning_tokens")},
        "cost": estimate_standard_cost(model_id, input_tokens, output_tokens,
                                       _get(input_details, "cached_tokens", 0), _get(response, "service_tier", "default")),
    }


def estimate_standard_cost(model_id, input_tokens, output_tokens, cached_tokens=0, service_tier="default"):
    """Dated USD estimate for documented standard, short-context text pricing.

    Unknown usage/pricing is null, never zero. Excludes tools, cache writes,
    alternate service tiers and >272K input pricing; not an invoice.
    """
    rates = {"gpt-4o-mini": (0.15, 0.075, 0.60), "gpt-5.6-terra": (2, 0.2, 12),
             "gpt-5.6-sol": (4, 0.4, 20), "gpt-6-astra": (10, 1, 50)}
    unknown = {"status": "not_priced", "amount": None, "currency": "USD"}
    if (model_id not in rates or input_tokens is None or output_tokens is None or
            input_tokens > 272000 or service_tier not in {None, "default", "standard"}):
        return unknown
    cached_tokens = cached_tokens or 0
    if min(input_tokens, output_tokens, cached_tokens) < 0 or cached_tokens > input_tokens:
        return unknown
    inp, cached, out = rates[model_id]
    return {"status": "estimated_standard_text", "amount": round(
        ((input_tokens - cached_tokens) * inp + cached_tokens * cached + output_tokens * out) / 1000000, 8),
        "currency": "USD", "pricing_date": "2026-09-05",
        "source": "https://developers.openai.com/api/docs/models/" + model_id}


class OpenAIChatCompletionsAdapter:
    """OpenAI implementation of L's provider-neutral model interface."""

    provider = "openai"

    def __init__(self, client, model_id: str):
        self.client = client
        self.model_id = str(model_id or "")
        self.available = client is not None and bool(self.model_id)

    def generate(self, request: dict) -> dict:
        if not self.available:
            raise RuntimeError("openai_adapter_unavailable")
        options = {
            "model": self.model_id,
            "messages": request["messages"],
            "store": False,
        }
        capabilities = model_capabilities(self.model_id)
        if capabilities["supports_temperature"]:
            options["temperature"] = request["temperature"]
        if request.get("max_output_tokens") is not None:
            options["max_completion_tokens" if capabilities["reasoning"] else "max_tokens"] = request["max_output_tokens"]
        if request.get("response_format"):
            options["response_format"] = request["response_format"]
        started = monotonic()
        response = self.client.chat.completions.create(**options)
        choice = response.choices[0]
        finish = _get(choice, "finish_reason", "stop")
        status = "complete" if finish == "stop" and not _get(choice.message, "refusal") else "incomplete"
        return {
            "status": status,
            "content": choice.message.content or "",
            "provider": self.provider,
            "model_id": _get(response, "model") or self.model_id,
            "receipt": model_receipt(response, model_id=self.model_id, api="chat_completions", status=status, started=started),
        }


class OpenAIResponsesAdapter:
    """Stateless text/image Responses transport; L retains memory and governance."""

    provider = "openai"

    def __init__(self, client, model_id: str, *, reasoning_effort="low"):
        self.client = client
        self.model_id = str(model_id or "")
        self.available = client is not None and bool(self.model_id)
        self.capabilities = model_capabilities(self.model_id)
        self.reasoning_effort = reasoning_effort
        if self.capabilities["reasoning"] and reasoning_effort not in self.capabilities["reasoning_efforts"]:
            raise ValueError("unsupported_reasoning_effort")

    def generate(self, request: dict) -> dict:
        inputs = []
        for message in request["messages"]:
            if message["role"] == "tool":
                raise ValueError("tool_messages_not_supported_by_l_adapter")
            content = message["content"]
            if isinstance(content, list):
                parts = []
                for part in content:
                    if part.get("type") == "text":
                        parts.append({"type": "input_text", "text": part["text"]})
                    elif part.get("type") == "image_url" and self.capabilities["images"] and message["role"] == "user":
                        image = part["image_url"]
                        parts.append({"type": "input_image", "image_url": image["url"], "detail": image.get("detail", "auto")})
                    else:
                        raise ValueError("unsupported_model_content")
                content = parts
            inputs.append({"role": message["role"], "content": content})
        options = {"model": self.model_id, "input": inputs, "store": False,
                   "max_output_tokens": request.get("max_output_tokens", 8192)}
        if self.capabilities["reasoning"]:
            options["reasoning"] = {"effort": self.reasoning_effort}
        elif self.capabilities["supports_temperature"]:
            options["temperature"] = request["temperature"]
        fmt = request.get("response_format")
        if fmt:
            if fmt["type"] == "json_schema":
                fmt = {"type": "json_schema", **fmt["json_schema"]}
            options["text"] = {"format": fmt}
        started = monotonic()
        response = self.client.responses.create(**options)
        status = "complete" if _get(response, "status") == "completed" else str(_get(response, "status") or "incomplete")
        outputs = _get(response, "output", []) or []
        if any(_get(part, "type") == "refusal" for item in outputs for part in (_get(item, "content", []) or [])):
            status = "refused"
        if any(_get(item, "type") not in {"message", "reasoning"} for item in outputs):
            status = "unsupported_output"
        return {"status": status, "content": _get(response, "output_text", "") or "",
                "provider": self.provider, "model_id": _get(response, "model") or self.model_id,
                "receipt": model_receipt(response, model_id=self.model_id, api="responses", status=status,
                                         started=started, effort=self.reasoning_effort if self.capabilities["reasoning"] else None)}


def create_model_adapter(client, model_id, *, api="auto", reasoning_effort="low"):
    if client is None:
        return UnavailableModelAdapter(model_id)
    api = model_capabilities(model_id)["api"] if api == "auto" else api
    if api == "responses":
        return OpenAIResponsesAdapter(client, model_id, reasoning_effort=reasoning_effort)
    if api == "chat_completions":
        return OpenAIChatCompletionsAdapter(client, model_id)
    raise ValueError("unsupported_model_api")


class UnavailableModelAdapter:
    provider = "unavailable"
    available = False

    def __init__(self, model_id: str = ""):
        self.model_id = str(model_id or "unconfigured")

    def generate(self, request: dict) -> dict:
        raise RuntimeError("model_adapter_unavailable")


def build_model_independence_packet(adapter: ModelAdapter | None) -> dict:
    """Describe the stable boundary without exposing credentials or prompts."""
    provider = str(getattr(adapter, "provider", "unavailable"))
    model_id = str(getattr(adapter, "model_id", "unconfigured"))
    available = bool(getattr(adapter, "available", False))
    contract = {
        "interface_version": MODEL_INTERFACE_VERSION,
        "request_fields": [
            "interface_version", "purpose", "messages", "temperature",
            "max_output_tokens", "response_format",
        ],
        "result_fields": [
            "interface_version", "status", "content", "provider", "model_id", "purpose",
        ],
        "persistent_systems": list(PERSISTENT_SYSTEMS),
        "replaceable_layer": "foundation_model_adapter",
    }
    fingerprint = sha256(
        json.dumps(contract, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "engine": "model_independence_layer",
        "version": MODEL_INTERFACE_VERSION,
        "status": "ready" if available else "adapter_unavailable",
        "active_adapter": {
            "provider": provider,
            "model_id": model_id,
            "available": available,
            "capabilities": model_capabilities(model_id),
            "routing": getattr(adapter, "routing_manifest", {"status": "single_model"}),
        },
        "contract": contract,
        "contract_fingerprint": fingerprint,
        "governance": {
            "foundation_model_is_replaceable": True,
            "foundation_model_owns_identity": False,
            "foundation_model_owns_memory": False,
            "foundation_model_owns_evidence": False,
            "foundation_model_can_bypass_governance": False,
            "provider_swap_requires_cognitive_code_change": False,
            "persistent_systems_survive_model_swap": True,
        },
    }


__all__ = [
    "MODEL_INTERFACE_VERSION",
    "PERSISTENT_SYSTEMS",
    "ModelAdapter",
    "OpenAIChatCompletionsAdapter",
    "UnavailableModelAdapter",
    "build_model_independence_packet",
    "build_model_request",
    "invoke_model",
]
