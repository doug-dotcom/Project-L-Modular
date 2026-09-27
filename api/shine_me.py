"""Owner-only context endpoint for the native Shine-Me companion."""

import os
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.cognition.shine_me_service import (
    answer_from_shine_me_context,
    prepare_shine_me_context,
    shine_me_binding_status,
)


class ContextRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


class CorrectionRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    expected_source: str = Field(min_length=1, max_length=160)
    issue_kind: str = Field(pattern="^(wrong|incomplete)$")
    proposed_correction: str = Field(min_length=1, max_length=2000)


def routes(retrieve, cognize, check_freshness, save_correction: Callable[[dict], object] | None = None) -> APIRouter:
    router = APIRouter(tags=["shine-me"])

    def approved_context(payload: ContextRequest, request: Request) -> dict:
        # /shine-me/context is protected by the server's account middleware.
        # Require the account state as a second boundary: a recovery token is
        # never an identity and user_id is never accepted in the request body.
        try:
            return prepare_shine_me_context(
                query=payload.query,
                verified_account=getattr(request.state, "account", None),
                configured_owner_id=os.getenv("PROJECT_L_OWNER_ID", ""),
                configured_memory_owner_id=os.getenv("L_MEMORY_OWNER_ID", ""),
                retrieve=retrieve,
                cognize=cognize,
                check_freshness=check_freshness,
            )
        except PermissionError as exc:
            raise HTTPException(403, "This account cannot access Shine-Me memory.") from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(503, "Shine-Me context is temporarily unavailable.") from exc

    @router.get("/shine-me/binding")
    def binding(request: Request) -> dict:
        try:
            return shine_me_binding_status(
                verified_account=getattr(request.state, "account", None),
                configured_owner_id=os.getenv("PROJECT_L_OWNER_ID", ""),
                configured_memory_owner_id=os.getenv("L_MEMORY_OWNER_ID", ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, "This account cannot access Shine-Me memory.") from exc
        except RuntimeError as exc:
            raise HTTPException(503, "Shine-Me owner binding is unavailable.") from exc

    @router.post("/shine-me/context")
    def context(payload: ContextRequest, request: Request) -> dict:
        return approved_context(payload, request)

    @router.post("/shine-me/ask")
    def ask(payload: ContextRequest, request: Request) -> dict:
        return answer_from_shine_me_context(approved_context(payload, request))

    @router.post("/shine-me/corrections")
    def submit_correction(payload: CorrectionRequest, request: Request) -> dict:
        # Recheck the verified owner and publication gates at submission time.
        # Browser-supplied source text is only an expected match, never authority.
        context = approved_context(ContextRequest(query=payload.query), request)
        answer = answer_from_shine_me_context(context)
        evidence = answer.get("evidence") or []
        if not evidence or evidence[0].get("source") != payload.expected_source:
            raise HTTPException(409, "The sourced answer changed. Ask again before submitting.")
        if not os.getenv("SUPABASE_SERVICE_ROLE_KEY") or save_correction is None:
            raise HTTPException(503, "Correction review is temporarily unavailable.")
        owner_id = str(os.getenv("PROJECT_L_OWNER_ID") or "").strip()
        row = {
            "owner_id": owner_id,
            "question": payload.query.strip(),
            "source": evidence[0]["source"],
            "provenance": evidence[0].get("provenance", "unknown"),
            "original_reply": answer["reply"],
            "issue_kind": payload.issue_kind,
            "proposed_correction": payload.proposed_correction.strip(),
        }
        if not row["proposed_correction"]:
            raise HTTPException(400, "Correction cannot be blank.")
        try:
            saved = save_correction(row)
            data = getattr(saved, "data", None)
            if not isinstance(data, list) or len(data) != 1 or not data[0].get("id"):
                raise RuntimeError("Correction receipt missing")
            return {"status": "pending_review", "id": str(data[0]["id"])}
        except Exception as exc:
            raise HTTPException(503, "Correction could not be saved for review.") from exc

    return router
