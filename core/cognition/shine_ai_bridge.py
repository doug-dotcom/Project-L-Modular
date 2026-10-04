"""Signed Project L -> Shine-AI model bridge.

Project L keeps identity, memory, evidence and cognition ownership. Shine-AI owns
provider selection/execution and its operational controls. Text requests fail
closed through Shine-AI; only request shapes Shine-AI cannot represent yet
(multimodal/tool-message payloads or unsupported response formats) may use the
explicit local fallback adapter.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from time import monotonic
from typing import Any, Callable
from urllib.parse import urlparse
from uuid import uuid4

import httpx


class ShineAIBridgeError(RuntimeError):
    """A signed Shine-AI inference request could not complete safely."""


class ShineAIModelAdapter:
    provider = "shine-ai"
    model_id = "shine-ai-router"
    available = True

    def __init__(
        self,
        *,
        base_url: str,
        app_id: str,
        key_id: str,
        secret: str,
        owner_id: str | None = None,
        fallback=None,
        timeout_seconds: float = 60.0,
        post_impl: Callable[..., Any] | None = None,
        now: Callable[[], float] = time.time,
        nonce_factory: Callable[[], str] | None = None,
    ) -> None:
        parsed = urlparse(str(base_url or "").strip())
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("shine_ai_url_invalid")
        if parsed.path not in {"", "/"}:
            raise ValueError("shine_ai_url_must_be_origin")
        if not app_id or not key_id or len(str(secret or "")) < 32:
            raise ValueError("shine_ai_credentials_invalid")
        if timeout_seconds < 1 or timeout_seconds > 120:
            raise ValueError("shine_ai_timeout_invalid")

        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        self.app_id = str(app_id)
        self.key_id = str(key_id)
        self._secret = str(secret).encode("utf-8")
        self.owner_id = str(owner_id or "") or None
        self.fallback = fallback
        self.timeout_seconds = float(timeout_seconds)
        self._post = post_impl or httpx.post
        self._now = now
        self._nonce_factory = nonce_factory or (lambda: uuid4().hex)
        self.routing_manifest = {
            "status": "shine_ai_shared_intelligence",
            "text_transport": "signed_fail_closed",
            "unsupported_content_fallback": bool(
                fallback is not None and getattr(fallback, "available", False)
            ),
            "memory_owner": "project-l",
            "direct_shine_ai_memory": False,
        }

    @staticmethod
    def _unsupported_reason(request: dict) -> str | None:
        messages = request.get("messages")
        if not isinstance(messages, list) or not messages:
            return "messages_missing"
        for message in messages:
            if not isinstance(message, dict):
                return "message_invalid"
            if message.get("role") not in {"system", "user", "assistant"}:
                return "tool_message_not_supported"
            if not isinstance(message.get("content"), str):
                return "multimodal_content_not_supported"

        response_format = request.get("response_format")
        if response_format is not None:
            if (
                not isinstance(response_format, dict)
                or response_format.get("type") != "json_object"
            ):
                return "response_format_not_supported"
        return None

    @staticmethod
    def _deep_route(request: dict) -> bool:
        purpose = str(
            request.get("routing_purpose")
            or request.get("purpose")
            or ""
        ).casefold()
        return any(
            token in purpose
            for token in (
                "recall",
                "report",
                "rike",
                "reason",
                "evidence",
                "claim",
                "publication",
                "benchmark",
            )
        )

    @staticmethod
    def _task_text(request: dict) -> str:
        for message in reversed(request.get("messages") or []):
            if message.get("role") == "user" and isinstance(message.get("content"), str):
                return message["content"].strip()[:20_000] or "Project L governed inference"
        return str(request.get("purpose") or "Project L governed inference")[:20_000]

    def _body(self, request: dict) -> dict:
        response_format = request.get("response_format") or {}
        json_mode = response_format.get("type") == "json_object"
        deep = self._deep_route(request)

        body: dict[str, Any] = {
            "app": self.app_id,
            "task": self._task_text(request),
            "capabilities": ["project-l-governed-inference"],
            "trusted_messages": [
                {
                    "role": str(message["role"]),
                    "content": str(message["content"]),
                }
                for message in request["messages"]
            ],
            "trusted_output_mode": "json_object" if json_mode else "text",
            "routing": {
                "tier": "deep" if deep or json_mode else "auto",
                "requires_reasoning": bool(deep or json_mode),
                "high_stakes": False,
                "cost_sensitive": False,
            },
            "budget": {
                "max_model_calls": 1,
            },
            "cache": {
                "allow_response_cache": False,
                "ttl_seconds": 300,
            },
            "metadata": {
                "sourceSystem": "project-l",
                "modelInterfaceVersion": request.get("interface_version"),
                "lPurpose": request.get("purpose"),
                "lRoutingPurpose": request.get("routing_purpose"),
                "lRequestSha256": request.get("request_sha256"),
                "memoryOwner": "project-l",
                "directMemoryDelegated": False,
            },
            "idempotency_key": (
                "l:" + str(request.get("request_sha256") or hashlib.sha256(
                    json.dumps(request, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest())
            )[:128],
        }
        if self.owner_id:
            body["user_id"] = self.owner_id

        requested_output = request.get("max_output_tokens")
        if requested_output is not None:
            body["budget"]["max_output_tokens"] = max(64, min(8192, int(requested_output)))
        elif json_mode:
            # L's evidence-backed JSON answers can be substantially longer than
            # ordinary conversation and are later verified by L itself.
            body["budget"]["max_output_tokens"] = 8192

        return body

    def _headers(self, body_bytes: bytes) -> dict[str, str]:
        timestamp = str(int(self._now()))
        nonce = str(self._nonce_factory())
        path = "/v1/respond"
        signed = b"\n".join(
            [
                self.app_id.encode("utf-8"),
                self.key_id.encode("utf-8"),
                timestamp.encode("ascii"),
                nonce.encode("utf-8"),
                b"POST",
                path.encode("ascii"),
                body_bytes,
            ]
        )
        signature = hmac.new(self._secret, signed, hashlib.sha256).hexdigest()
        return {
            "Content-Type": "application/json",
            "X-Shine-App": self.app_id,
            "X-Shine-Key-Id": self.key_id,
            "X-Shine-Timestamp": timestamp,
            "X-Shine-Nonce": nonce,
            "X-Shine-Signature": signature,
        }

    def _fallback_generate(self, request: dict, reason: str) -> dict:
        if self.fallback is None or not getattr(self.fallback, "available", False):
            raise ShineAIBridgeError("shine_ai_request_shape_not_supported")
        result = self.fallback.generate(request)
        if not isinstance(result, dict):
            raise ShineAIBridgeError("shine_ai_fallback_result_invalid")
        receipt = dict(result.get("receipt") or {})
        receipt["shine_ai_bridge"] = {
            "version": "1.0",
            "status": "explicit_local_fallback",
            "reason": reason,
            "network_failure_fallback": False,
        }
        return {**result, "receipt": receipt}

    def generate(self, request: dict) -> dict:
        unsupported = self._unsupported_reason(request)
        if unsupported:
            return self._fallback_generate(request, unsupported)

        body = self._body(request)
        body_bytes = json.dumps(
            body,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        headers = self._headers(body_bytes)

        started = monotonic()
        try:
            response = self._post(
                self.base_url + "/v1/respond",
                content=body_bytes,
                headers=headers,
                timeout=self.timeout_seconds,
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            raise ShineAIBridgeError("shine_ai_unavailable") from exc

        if int(getattr(response, "status_code", 500)) != 200:
            status = int(getattr(response, "status_code", 500))
            reason = "request_rejected"
            if status == 403:
                try:
                    detail = response.json().get("detail", "")
                except Exception:
                    detail = ""
                if isinstance(detail, str):
                    if detail.endswith("has no Shine-AI policy."):
                        reason = "app_policy_missing"
                    elif "trusted companion prompt envelope" in detail:
                        reason = "trusted_prompt_not_permitted"
                    elif "requires an approved prompt profile" in detail:
                        reason = "prompt_profile_required"
                    else:
                        reason = "permission_denied"
            error = ShineAIBridgeError("shine_ai_request_rejected_" + str(status))
            # Only fixed reason codes and non-secret app identity enter receipts.
            # Never persist upstream bodies, headers, credentials or prompt text.
            error.receipt = {
                "status": "failed",
                "error_type": "ShineAIBridgeError",
                "provider_status": status,
                "app_id": self.app_id,
                "reason": reason,
            }
            raise error

        try:
            payload = response.json()
        except Exception as exc:
            raise ShineAIBridgeError("shine_ai_response_invalid") from exc
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            raise ShineAIBridgeError("shine_ai_response_invalid")

        answer = payload.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise ShineAIBridgeError("shine_ai_answer_missing")

        delivery = payload.get("delivery")
        if isinstance(delivery, dict) and delivery.get("mode") == "withheld":
            raise ShineAIBridgeError("shine_ai_delivery_withheld")

        efficiency = payload.get("efficiency") if isinstance(payload.get("efficiency"), dict) else {}
        model = str(payload.get("model") or "shine-ai-router")
        model_tier = payload.get("model_tier")
        reasoning_effort = payload.get("reasoning_effort")

        return {
            "status": "complete",
            "content": answer,
            "provider": self.provider,
            "model_id": model,
            "receipt": {
                "version": "1.0",
                "provider": self.provider,
                "requested_model": self.model_id,
                "model_id": model,
                "api": "shine-ai-v1",
                "response_id": payload.get("request_id"),
                "status": "complete",
                "duration_ms": round((monotonic() - started) * 1000),
                "reasoning_effort": reasoning_effort,
                "usage": {
                    "input_tokens": efficiency.get("input_tokens"),
                    "output_tokens": efficiency.get("output_tokens"),
                    "total_tokens": efficiency.get("total_tokens"),
                    "cached_input_tokens": efficiency.get("cached_input_tokens"),
                    "reasoning_tokens": None,
                },
                "cost": {
                    "status": "estimated_by_shine_ai",
                    "amount": efficiency.get("estimated_cost_usd"),
                    "currency": "USD",
                },
                "shine_ai_bridge": {
                    "version": "1.0",
                    "status": "complete",
                    "service_request_id": payload.get("request_id"),
                    "route": payload.get("route"),
                    "reason": payload.get("reason"),
                    "model_tier": model_tier,
                    "reasoning_effort": reasoning_effort,
                    "idempotency_replayed": payload.get("idempotency_replayed", False),
                    "delivery": delivery,
                    "verification_owner": "project-l",
                    "network_failure_fallback": False,
                },
            },
        }


__all__ = ["ShineAIBridgeError", "ShineAIModelAdapter"]
