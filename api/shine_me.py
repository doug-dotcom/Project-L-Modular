"""Owner-only context endpoint for the native Shine-Me companion."""

import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from core.cognition.shine_me_service import prepare_shine_me_context


class ContextRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


def routes(retrieve, cognize) -> APIRouter:
    router = APIRouter(tags=["shine-me"])

    @router.post("/shine-me/context")
    def context(payload: ContextRequest, request: Request) -> dict:
        # /shine-me/context is protected by the server's account middleware.
        # Require the account state as a second boundary: a recovery token is
        # never an identity and user_id is never accepted in the request body.
        try:
            return prepare_shine_me_context(
                query=payload.query,
                verified_account=getattr(request.state, "account", None),
                configured_owner_id=os.getenv("PROJECT_L_OWNER_ID", ""),
                retrieve=retrieve,
                cognize=cognize,
            )
        except PermissionError as exc:
            raise HTTPException(403, "This account cannot access Shine-Me memory.") from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(503, "Shine-Me context is temporarily unavailable.") from exc

    return router
