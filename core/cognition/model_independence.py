"""Project L Phase 11: provider-neutral foundation-model interface.

The adapter owns provider syntax. L's durable cognition, memory, identity and
governance receive and emit stable packets that survive a model replacement.
"""

from __future__ import annotations

from hashlib import sha256
import json
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
    return {
        "interface_version": MODEL_INTERFACE_VERSION,
        "status": str(result.get("status") or "complete"),
        "content": content,
        "provider": str(result.get("provider") or getattr(adapter, "provider", "unknown")),
        "model_id": str(result.get("model_id") or getattr(adapter, "model_id", "unknown")),
        "purpose": str(request.get("purpose") or "general"),
    }


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
            "temperature": request["temperature"],
        }
        if request.get("max_output_tokens") is not None:
            options["max_tokens"] = request["max_output_tokens"]
        if request.get("response_format"):
            options["response_format"] = request["response_format"]
        response = self.client.chat.completions.create(**options)
        return {
            "status": "complete",
            "content": response.choices[0].message.content or "",
            "provider": self.provider,
            "model_id": self.model_id,
        }


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
