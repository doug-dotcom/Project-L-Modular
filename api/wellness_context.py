import hashlib
import os
import re
import secrets

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from api.shine_ai_memory import _BROAD_RECALL_RE, _owner_context


router = APIRouter(prefix="/internal/wellness", tags=["internal-wellness"])

CONTRACT = "shine-wellness/project-l-context-only-v1"
PURPOSE = "wellness-longitudinal-context"
AUTHORITY = "context_only"
_MAX_CONTEXT_RECORDS = 6
_REF = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$", re.IGNORECASE)


class WellnessContextRequest(BaseModel):
    request_contract: Literal["shine-wellness/project-l-context-only-v1"]
    purpose: Literal["wellness-longitudinal-context"]
    user_id: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=1, max_length=1_200)
    canonical_record_ids: list[str] = Field(min_length=1, max_length=8)
    permission_decision_id: str = Field(min_length=1, max_length=128)
    limit: int = Field(default=4, ge=1, le=_MAX_CONTEXT_RECORDS)

    @field_validator("canonical_record_ids")
    @classmethod
    def validate_canonical_record_ids(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("canonical record references must be unique")
        if any(not _REF.fullmatch(value or "") for value in values):
            raise ValueError("invalid canonical record reference")
        return values

    @field_validator("permission_decision_id")
    @classmethod
    def validate_permission_decision_id(cls, value: str) -> str:
        if not _REF.fullmatch(value or ""):
            raise ValueError("invalid permission decision reference")
        return value


class WellnessContextReference(BaseModel):
    id: str
    context_text: str
    source_table: Literal["memory_health"]
    source_id: str
    source_role: Literal["user", "assistant", "unknown"]
    owner_bound: Literal[True]
    authority: Literal["context_only"]
    fact_authority: Literal["none"]


class WellnessContextResponse(BaseModel):
    source: Literal["project-l"]
    contract: Literal["shine-wellness/project-l-context-only-v1"]
    version: Literal["1.0.0"]
    purpose: Literal["wellness-longitudinal-context"]
    context_id: str
    authority: Literal["context_only"]
    health_truth_authority: Literal[False]
    read_only: Literal[True]
    canonical_record_ids: list[str]
    permission_decision_id: str
    records: list[WellnessContextReference]
    receipt: dict[str, object]


def _configured_owner(service_token: str) -> str:
    expected_token = os.getenv("WELLNESS_CONTEXT_SERVICE_TOKEN", "").strip()
    owner_id = (
        os.getenv("L_MEMORY_OWNER_ID", "").strip()
        or os.getenv("PROJECT_L_OWNER_ID", "").strip()
    )

    if not expected_token or not owner_id:
        raise HTTPException(
            status_code=503,
            detail="Project L's Wellness context bridge is disabled.",
        )
    if len(expected_token) < 32:
        raise HTTPException(
            status_code=503,
            detail="Project L's Wellness context bridge is misconfigured.",
        )
    if (
        not service_token
        or not secrets.compare_digest(service_token, expected_token)
    ):
        raise HTTPException(status_code=401, detail="Invalid service credentials.")
    try:
        return str(UUID(owner_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Project L's Wellness owner binding is invalid.",
        ) from exc


def _validate_request(
    request: WellnessContextRequest,
    owner_id: str,
) -> None:
    try:
        request_owner = str(UUID(request.user_id))
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(
            status_code=403,
            detail="Wellness context owner mismatch.",
        ) from None
    if request_owner != owner_id:
        raise HTTPException(
            status_code=403,
            detail="Wellness context owner mismatch.",
        )
    if _BROAD_RECALL_RE.search(request.query):
        raise HTTPException(
            status_code=422,
            detail="Wellness context supports bounded targeted recall only.",
        )


def _context_records(
    context: dict,
    limit: int,
) -> list[WellnessContextReference]:
    rows = context.get("matches")
    if not isinstance(rows, list):
        raise HTTPException(
            status_code=503,
            detail="Project L returned invalid Wellness context.",
        )

    records: list[WellnessContextReference] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        if str(item.get("domain") or "").strip().lower() != "health":
            continue

        provenance = (
            item.get("provenance")
            if isinstance(item.get("provenance"), dict)
            else {}
        )
        if provenance.get("ownerBound") is not True:
            continue

        source_table = str(provenance.get("sourceTable") or "").strip()
        source_id = str(
            provenance.get("sourceId") or item.get("id") or ""
        ).strip()
        if source_table != "memory_health" or not source_id:
            continue

        context_text = str(item.get("content") or "").strip()
        if not context_text:
            continue

        source_role = str(
            provenance.get("sourceRole") or "unknown"
        ).strip().lower()
        if source_role not in {"user", "assistant"}:
            source_role = "unknown"

        records.append(
            WellnessContextReference(
                id=f"{source_table}:{source_id}"[:128],
                context_text=context_text[:1_200],
                source_table="memory_health",
                source_id=source_id[:128],
                source_role=source_role,
                owner_bound=True,
                authority="context_only",
                fact_authority="none",
            )
        )
        if len(records) >= limit:
            break
    return records


def _context_id(
    *,
    owner_id: str,
    permission_decision_id: str,
    canonical_record_ids: list[str],
    record_ids: list[str],
) -> str:
    material = "\x1f".join(
        [
            owner_id,
            permission_decision_id,
            *canonical_record_ids,
            *record_ids,
        ]
    )
    return "lctx:" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


@router.post(
    "/context",
    response_model=WellnessContextResponse,
)
def retrieve_wellness_context(
    request: WellnessContextRequest,
    x_wellness_service_token: str = Header(default=""),
) -> WellnessContextResponse:
    owner_id = _configured_owner(x_wellness_service_token)
    _validate_request(request, owner_id)

    # Bias the existing hardened owner-scoped retrieval engine toward the
    # dedicated health memory family, then filter again before disclosure.
    context = _owner_context(
        owner_id,
        f"health {request.query}",
        _MAX_CONTEXT_RECORDS,
    )
    records = _context_records(context, request.limit)

    scope = (
        context.get("scope")
        if isinstance(context.get("scope"), dict)
        else {}
    )
    query_binding = (
        context.get("_queryBinding")
        if isinstance(context.get("_queryBinding"), dict)
        else {}
    )
    record_ids = [record.id for record in records]

    return WellnessContextResponse(
        source="project-l",
        contract=CONTRACT,
        version="1.0.0",
        purpose=PURPOSE,
        context_id=_context_id(
            owner_id=owner_id,
            permission_decision_id=request.permission_decision_id,
            canonical_record_ids=request.canonical_record_ids,
            record_ids=record_ids,
        ),
        authority=AUTHORITY,
        health_truth_authority=False,
        read_only=True,
        canonical_record_ids=[*request.canonical_record_ids],
        permission_decision_id=request.permission_decision_id,
        records=records,
        receipt={
            "status": str(context.get("status") or "unknown"),
            "records_returned": len(records),
            "requested_domain": "health",
            "owner_bound": scope.get("ownerBound") is True,
            "permission_reference_bound": True,
            "canonical_reference_bound": True,
            "bounded": True,
            "read_only": True,
            "writes_performed": False,
            "broad_recall_allowed": False,
            "health_truth_authority": False,
            "query_binding": str(query_binding.get("mode") or "unknown"),
            "query_contract_version": str(
                query_binding.get("queryContractVersion") or ""
            ),
        },
    )
