import os
import re
import secrets
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from agents.rhee.rhee_v3 import build_context_packet as build_rhee_packet

router = APIRouter(prefix="/internal/shine-ai", tags=["internal-shine-ai"])

# Project L is currently a single-owner corpus. This policy deliberately starts
# with one consumer and narrow curated scopes. Expansion must be explicit.
_APP_SCOPE_POLICY: dict[str, frozenset[str]] = {
    "shine-dive": frozenset({"episodic", "sport", "general"}),
}

_BROAD_RECALL_RE = re.compile(
    r"\b(?:deep recall|all memories|every memory|everything you know|"
    r"entire memory|whole memory|complete history|full history|list all|find the rest)\b",
    re.IGNORECASE,
)

Priority = Literal["high", "normal", "low"]


class MemoryRetrieveRequest(BaseModel):
    app: str = Field(min_length=1, max_length=100)
    user_id: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=1, max_length=2_000)
    scopes: list[str] = Field(min_length=1, max_length=6)
    limit: int = Field(default=4, ge=1, le=6)


class MemoryRecordResponse(BaseModel):
    id: str
    text: str
    tags: list[str]
    priority: Priority


class MemoryRetrieveResponse(BaseModel):
    source: Literal["project-l"]
    engine: str
    version: str
    recall_active: bool
    records: list[MemoryRecordResponse]
    receipt: dict[str, object]


def _configured_owner(service_token: str) -> str:
    expected_token = os.getenv("SHINE_AI_MEMORY_TOKEN", "").strip()
    owner_id = os.getenv("PROJECT_L_OWNER_ID", "").strip()

    if not expected_token or not owner_id:
        raise HTTPException(
            status_code=503,
            detail="Project L's Shine-AI memory bridge is disabled.",
        )
    if len(expected_token) < 32:
        raise HTTPException(
            status_code=503,
            detail="Project L's Shine-AI memory bridge is misconfigured.",
        )

    if not service_token or not secrets.compare_digest(service_token, expected_token):
        raise HTTPException(status_code=401, detail="Invalid service credentials.")

    return owner_id


def _scope_for_source(source: str) -> str | None:
    table = str(source or "").split(":", 1)[0].strip().lower()

    if table == "episodic_memories":
        return "episodic"
    if table == "identity_anchors":
        return "identity"
    if table.startswith("memory_"):
        return table.removeprefix("memory_")
    return None


def _priority_for_role(role: str) -> Priority:
    role = str(role or "").strip().lower()
    if role == "user":
        return "high"
    if role in {"assistant", "model"}:
        return "low"
    return "normal"


def _validate_access(request: MemoryRetrieveRequest, owner_id: str) -> frozenset[str]:
    if request.user_id != owner_id:
        raise HTTPException(status_code=403, detail="Memory owner mismatch.")

    allowed_scopes = _APP_SCOPE_POLICY.get(request.app)
    if allowed_scopes is None:
        raise HTTPException(status_code=403, detail="App is not authorised for Project L memory.")

    requested = set(request.scopes)
    denied = requested - allowed_scopes
    if denied:
        raise HTTPException(
            status_code=403,
            detail=f"Requested memory scope is not authorised: {', '.join(sorted(denied))}.",
        )

    if _BROAD_RECALL_RE.search(request.query):
        raise HTTPException(
            status_code=422,
            detail="The service memory bridge only supports bounded targeted recall.",
        )

    return frozenset(requested)


@router.post("/memory/retrieve", response_model=MemoryRetrieveResponse)
def retrieve_memory(
    request: MemoryRetrieveRequest,
    x_shine_service_token: str = Header(default=""),
) -> MemoryRetrieveResponse:
    owner_id = _configured_owner(x_shine_service_token)
    requested_scopes = _validate_access(request, owner_id)

    try:
        packet = build_rhee_packet(request.query)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Project L retrieval is temporarily unavailable.",
        ) from exc

    if not isinstance(packet, dict):
        raise HTTPException(status_code=503, detail="Project L returned an invalid retrieval packet.")

    evidence = packet.get("evidence") or []
    if not isinstance(evidence, list):
        raise HTTPException(status_code=503, detail="Project L returned invalid evidence.")

    records: list[MemoryRecordResponse] = []
    seen_sources: set[str] = set()
    seen_text: set[str] = set()

    for item in evidence:
        if not isinstance(item, dict):
            continue

        source = str(item.get("source") or "").strip()
        scope = _scope_for_source(source)
        if not source or scope not in requested_scopes:
            continue

        text = str(item.get("quote_source") or "").strip()
        if not text:
            continue

        text = text[:1_800]
        fingerprint = " ".join(text.lower().split())
        if source in seen_sources or fingerprint in seen_text:
            continue

        seen_sources.add(source)
        seen_text.add(fingerprint)

        role = str(item.get("role") or "").strip().lower()
        records.append(
            MemoryRecordResponse(
                id=source[:80],
                text=text,
                tags=[scope, role or "unknown", "rhee"],
                priority=_priority_for_role(role),
            )
        )
        if len(records) >= request.limit:
            break

    recall_plan = packet.get("recall_plan")
    recall_status = recall_plan.get("status") if isinstance(recall_plan, dict) else None

    return MemoryRetrieveResponse(
        source="project-l",
        engine=str(packet.get("engine") or "rhee"),
        version=str(packet.get("version") or "unknown"),
        recall_active=bool(packet.get("recall_active")),
        records=records,
        receipt={
            "status": recall_status or "unknown",
            "requested_scopes": sorted(requested_scopes),
            "evidence_considered": len(evidence),
            "records_returned": len(records),
            "bounded": True,
            "read_only": True,
        },
    )
