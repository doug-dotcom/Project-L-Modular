"""Narrow service bridge: Wellness validates its own owner session before calling.

This bridge submits conversation only; it does not run Shine preflight, import
canonical health records, or change the read-only wellness context contract.
"""
import hashlib
import hmac
import os
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/internal/wellness/chat")
_store = None


def register_wellness_chat_store(store):
    global _store
    _store = store


def boundary(token, owner):
    configured = os.getenv("WELLNESS_CHAT_SERVICE_TOKEN", "")
    configured_owner = os.getenv("WELLNESS_CHAT_OWNER_ID", "")
    if len(configured) < 32 or not configured_owner or _store is None:
        raise HTTPException(503, "Wellness conversation is not configured.")
    if not hmac.compare_digest(token, configured):
        raise HTTPException(401, "Service credential required.")
    if str(owner) != configured_owner:
        raise HTTPException(403, "Wellness owner mismatch.")
    return hmac.new(configured.encode(), ("wellness-chat:" + configured_owner).encode(), hashlib.sha256).hexdigest()


class WellnessChatRequest(BaseModel):
    user_id: UUID
    request_id: UUID
    conversation_id: UUID
    message: str = Field(min_length=1, max_length=6000)


@router.post("/start")
def start(request: WellnessChatRequest, x_wellness_chat_token: str = Header(default="")):
    recovery = boundary(x_wellness_chat_token, request.user_id)
    if not request.message.strip():
        raise HTTPException(422, "Write a message first.")
    # Stable envelope is required for durable duplicate/conflict detection.
    envelope = {
        "request_id": str(request.request_id),
        "conversation_id": "wellness_" + str(request.conversation_id),
        "message": (
            "[Shine Wellness: Talk it through. Respond conversationally and warmly in Australian English. "
            "Help Doug reflect, ask a useful follow-up when appropriate, and keep health context provisional. "
            "This is a conversation, not an instruction to operate other applications or update health records.]\n\n"
            + request.message.strip()
        ),
    }
    try:
        result = _store.submit(envelope, recovery)
    except Exception as exc:
        raise HTTPException(503, "L could not confirm the message. Retry with the same request ID.") from exc
    if result.get("status") in {"invalid", "conflict", "not_found"}:
        raise HTTPException(409, "Message identity could not be confirmed.")
    return {"status": result.get("status", "pending"), "durable": True}


@router.get("/result/{request_id}")
def result(request_id: UUID, user_id: UUID, x_wellness_chat_token: str = Header(default="")):
    recovery = boundary(x_wellness_chat_token, user_id)
    try:
        saved = _store.get(str(request_id), recovery)
    except Exception as exc:
        raise HTTPException(503, "The saved answer is temporarily unavailable.") from exc
    status = saved.get("status", "pending")
    payload = saved.get("result") or {}
    if status == "ready" and isinstance(payload, dict) and isinstance(payload.get("reply"), str) and not payload.get("error"):
        return {"status": "ready", "reply": payload["reply"]}
    if status in {"failed", "interrupted", "invalid"} or payload.get("error"):
        return {"status": "failed"}
    return {"status": status}
