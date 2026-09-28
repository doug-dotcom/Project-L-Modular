"""Authenticated owner-facing status/control for Foundation connection authority."""

import os
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from services.foundation_companion_service import (
    ensure_foundation_delegation,
    foundation_account_owner,
    foundation_connection_status,
    foundation_fleet_status,
    list_delayed_completion_history,
    safe_connection_result,
)


class CompletionAck(BaseModel):
    lease_token: str


def routes(db) -> APIRouter:
    router = APIRouter(prefix="/foundation", tags=["foundation"])

    def owner_id(request: Request) -> str:
        account = getattr(request.state, "account", None)
        user_id = str((account or {}).get("user_id") or "")
        configured = foundation_account_owner(db)
        if not user_id or not configured or user_id != configured:
            raise HTTPException(403, "This account cannot access the Foundation connection.")
        return user_id

    @router.get("/connection")
    def connection(request: Request) -> dict:
        try:
            return foundation_connection_status(db, owner_id(request))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, "Foundation connection status is temporarily unavailable.") from exc

    @router.post("/refresh")
    def refresh(request: Request) -> dict:
        try:
            result = ensure_foundation_delegation(db, owner_id(request))
            return safe_connection_result(result)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, "Foundation delegation refresh is temporarily unavailable.") from exc

    @router.get("/fleet")
    def fleet(request: Request) -> dict:
        try:
            return foundation_fleet_status(db, owner_id(request))
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(503, "Concierge specialist status is temporarily unavailable.") from exc

    @router.get("/completions/history")
    def completion_history(
        request: Request,
        limit: int = 100,
    ) -> dict:
        try:
            return list_delayed_completion_history(
                db,
                owner_id(request),
                limit=limit,
            )
        except HTTPException:
            raise
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                503, "Delayed Concierge answer history is temporarily unavailable."
            ) from exc

    @router.post("/completions/claim")
    def claim_completion(request: Request) -> dict:
        try:
            result = db.rpc(
                "companion_claim_completion_event_v2",
                {"p_user_id": owner_id(request)},
            ).execute()
            data = getattr(result, "data", None)
            if not isinstance(data, dict):
                raise RuntimeError("completion-claim-invalid")
            return data
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                503, "Concierge completion status is temporarily unavailable."
            ) from exc

    @router.post("/completions/{event_id}/ack")
    def acknowledge_completion(
        event_id: str,
        payload: CompletionAck,
        request: Request,
    ) -> dict:
        try:
            event_uuid = str(UUID(event_id))
            lease_uuid = str(UUID(payload.lease_token))
        except ValueError as exc:
            raise HTTPException(400, "Valid completion and lease IDs are required.") from exc
        try:
            result = db.rpc(
                "companion_ack_completion_event_v2",
                {
                    "p_user_id": owner_id(request),
                    "p_event_id": event_uuid,
                    "p_lease_token": lease_uuid,
                },
            ).execute()
            data = getattr(result, "data", None)
            if not isinstance(data, dict):
                raise RuntimeError("completion-ack-invalid")
            return data
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                503, "Concierge completion acknowledgement is temporarily unavailable."
            ) from exc

    return router
