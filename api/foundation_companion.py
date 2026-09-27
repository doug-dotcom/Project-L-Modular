"""Authenticated owner-facing status/control for Foundation connection authority."""

import os

from fastapi import APIRouter, HTTPException, Request

from services.foundation_companion_service import (
    ensure_foundation_delegation,
    foundation_connection_status,
    safe_connection_result,
)


def routes(db) -> APIRouter:
    router = APIRouter(prefix="/foundation", tags=["foundation"])

    def owner_id(request: Request) -> str:
        account = getattr(request.state, "account", None)
        user_id = str((account or {}).get("user_id") or "")
        configured = str(os.getenv("PROJECT_L_OWNER_ID") or "").strip()
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

    return router
