import hashlib
import math
import os
import re
import secrets
import threading
import time

import httpx
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from supabase import create_client
from supabase.lib.client_options import SyncClientOptions

router = APIRouter(prefix="/internal/shine-ai", tags=["internal-shine-ai"])

# Every consumer gets an explicit narrow scope allow-list. Episodic remains in
# the Dive request contract for compatibility, but it is not returned until
# legacy episodic rows have explicit owner bindings.
_APP_SCOPE_POLICY: dict[str, frozenset[str]] = {
    "shine-dive": frozenset({"episodic", "sport", "general"}),
    "daash": frozenset({"sport"}),
}

_BROAD_RECALL_RE = re.compile(
    r"\b(?:deep recall|all memories|every memory|everything you know|"
    r"entire memory|whole memory|complete history|full history|list all|find the rest)\b",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STOP_TERMS = {
    "about", "am", "an", "and", "are", "as", "at", "be", "by", "can",
    "completed", "could", "did", "does", "for", "from", "have", "how", "in",
    "into", "is", "it", "know", "me", "more", "my", "of", "on", "or", "our",
    "please", "that", "the", "their", "them", "this", "to", "was", "we", "were",
    "what", "when", "where", "which", "who", "why", "with", "would", "you",
    "your",
}

Priority = Literal["high", "normal", "low"]
_db_client = None
_db_transport = None

# These are the two transient failures observed in production:
# - PGRST002: PostgREST could not build/query its schema cache.
# - 57014: Postgres cancelled one retrieval at the statement timeout.
# Keep retries deliberately narrow so auth, permission and contract failures
# are never retried. PGRST002 also opens a short process-local circuit after a
# failed retry to stop concurrent callers from hammering a recovering Data API.
_TRANSIENT_RPC_RETRY_DELAYS: dict[str, tuple[float, ...]] = {
    "PGRST002": (0.4,),
    "PGRST003": (0.25,),
    "57014": (0.2,),
    "HTTP_TIMEOUT": (0.25,),
}
_DATA_API_CIRCUIT_SECONDS = 8.0
_DATA_API_CIRCUIT_MAX_SECONDS = 60.0
_MAX_CONCURRENT_MEMORY_RPCS = 2
_RPC_BULKHEAD_WAIT_SECONDS = 0.25
_MEMORY_RPC_TIMEOUT_SECONDS = 6.0
_MEMORY_RPC_CONNECT_SECONDS = 3.0
_MEMORY_RPC_POOL_SECONDS = 1.0
_QUERY_CONTRACT_VERSION = "2"

_rpc_circuit_lock = threading.Lock()
_rpc_circuit_open_until = 0.0
_rpc_failure_streak = 0
_rpc_bulkhead = threading.BoundedSemaphore(_MAX_CONCURRENT_MEMORY_RPCS)
# Exactly one caller may test database recovery after an opened circuit cools down.
_rpc_half_open_probe = threading.Lock()


def _rpc_error_code(exc: Exception) -> str:
    if isinstance(
        exc,
        (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.PoolTimeout),
    ):
        return "HTTP_TIMEOUT"

    code = str(getattr(exc, "code", "") or "").strip().upper()
    if code:
        return code[:80]

    message = str(getattr(exc, "message", "") or str(exc) or "").upper()
    for candidate in _TRANSIENT_RPC_RETRY_DELAYS:
        if candidate in message:
            return candidate
    return ""


def _rpc_circuit_retry_after() -> int:
    with _rpc_circuit_lock:
        remaining = _rpc_circuit_open_until - time.monotonic()
    return max(1, math.ceil(remaining)) if remaining > 0 else 0


def _rpc_requires_half_open_probe() -> bool:
    with _rpc_circuit_lock:
        return (
            _rpc_failure_streak > 0
            and _rpc_circuit_open_until <= time.monotonic()
        )


def _rpc_runtime_snapshot() -> dict[str, object]:
    now = time.monotonic()
    with _rpc_circuit_lock:
        failure_streak = _rpc_failure_streak
        remaining = max(0.0, _rpc_circuit_open_until - now)

    if remaining > 0:
        circuit_state = "open"
    elif failure_streak > 0:
        circuit_state = "half-open"
    else:
        circuit_state = "closed"

    database_configured = bool(
        os.getenv("SUPABASE_URL", "").strip()
        and (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.getenv("SUPABASE_KEY", "").strip()
        )
    )
    if not database_configured:
        status = "degraded"
    elif circuit_state == "closed":
        status = "ready"
    else:
        status = "protected"

    return {
        "status": status,
        "circuit_state": circuit_state,
        "retry_after": max(1, math.ceil(remaining)) if remaining > 0 else 0,
        "failure_streak": failure_streak,
        "recovery_probe_in_progress": _rpc_half_open_probe.locked(),
        "database_configured": database_configured,
    }


def _open_rpc_circuit(seconds: float) -> None:
    global _rpc_circuit_open_until
    with _rpc_circuit_lock:
        _rpc_circuit_open_until = max(
            _rpc_circuit_open_until,
            time.monotonic() + max(0.0, seconds),
        )


def _escalate_rpc_circuit() -> int:
    """Increase outage backoff only after a transient RPC has fully failed."""
    global _rpc_circuit_open_until, _rpc_failure_streak
    with _rpc_circuit_lock:
        _rpc_failure_streak += 1
        seconds = min(
            _DATA_API_CIRCUIT_MAX_SECONDS,
            _DATA_API_CIRCUIT_SECONDS * (2 ** (_rpc_failure_streak - 1)),
        )
        _rpc_circuit_open_until = max(
            _rpc_circuit_open_until,
            time.monotonic() + seconds,
        )
    return int(seconds)


def _close_rpc_circuit() -> None:
    global _rpc_circuit_open_until, _rpc_failure_streak
    with _rpc_circuit_lock:
        _rpc_circuit_open_until = 0.0
        _rpc_failure_streak = 0


def _query_key(terms: list[str]) -> str:
    # Deterministic request/response cohort identifier only; not a security token.
    return hashlib.md5("\x1f".join(terms).encode("utf-8")).hexdigest()


def _safe_rpc_error(exc: Exception) -> str:
    """Return bounded operational error metadata without request data or credentials."""
    error_type = type(exc).__name__
    code = str(getattr(exc, "code", "") or "")[:80]
    message = str(getattr(exc, "message", "") or str(exc) or "")[:240]
    message = re.sub(r"(?i)(bearer|apikey|authorization|token|secret)\s*[:=]\s*\S+", r"\1=[redacted]", message)
    return f"type={error_type} code={code or '-'} message={message or '-'}"


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


class MemoryBridgeHealthResponse(BaseModel):
    source: Literal["project-l"]
    component: Literal["memory-bridge"]
    version: str
    status: Literal["ready", "protected", "degraded"]
    circuit_state: Literal["closed", "open", "half-open"]
    retry_after: int
    failure_streak: int
    recovery_probe_in_progress: bool
    database_configured: bool
    database_touched: Literal[False]
    max_concurrent_rpcs: int
    rpc_timeout_seconds: float
    rpc_connect_seconds: float
    rpc_pool_seconds: float
    read_only: Literal[True]
    fail_closed: Literal[True]


def _configured_owner(service_token: str) -> str:
    expected_token = os.getenv("SHINE_AI_MEMORY_TOKEN", "").strip()
    owner_id = (
        os.getenv("L_MEMORY_OWNER_ID", "").strip()
        or os.getenv("PROJECT_L_OWNER_ID", "").strip()
    )

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
    try:
        return str(UUID(owner_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Project L's memory owner binding is invalid.",
        ) from exc


def _validate_access(request: MemoryRetrieveRequest, owner_id: str) -> frozenset[str]:
    try:
        request_owner = str(UUID(request.user_id))
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(status_code=403, detail="Memory owner mismatch.") from None
    if request_owner != owner_id:
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


def _database():
    global _db_client, _db_transport
    if _db_client is not None:
        return _db_client
    url = os.getenv("SUPABASE_URL", "").strip()
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
    )
    if not url or not key:
        raise HTTPException(
            status_code=503,
            detail="Project L owner-scoped retrieval is not configured.",
        )

    # Match L's durable-ledger transport discipline. The default shared HTTP/2
    # pool has previously produced ambiguous protocol failures under Railway.
    # This bridge is read-only, so one bounded HTTP/1.1 client is safer and does
    # not change memory authority or retry semantics.
    _db_transport = httpx.Client(
        http2=False,
        timeout=httpx.Timeout(
            _MEMORY_RPC_TIMEOUT_SECONDS,
            connect=_MEMORY_RPC_CONNECT_SECONDS,
            pool=_MEMORY_RPC_POOL_SECONDS,
        ),
        limits=httpx.Limits(
            max_connections=4,
            max_keepalive_connections=2,
            keepalive_expiry=5,
        ),
    )
    try:
        _db_client = create_client(
            url,
            key,
            options=SyncClientOptions(
                httpx_client=_db_transport,
                auto_refresh_token=False,
                persist_session=False,
            ),
        )
    except Exception:
        _db_transport.close()
        _db_transport = None
        raise
    return _db_client


def _query_terms(query: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for token in _TOKEN_RE.findall(query.lower()):
        if len(token) < 2 or token in _STOP_TERMS or token in seen:
            continue
        seen.add(token)
        terms.append(token)
        if len(terms) >= 24:
            break
    return terms


def _owner_context(owner_id: str, query: str, limit: int) -> dict:
    terms = _query_terms(query)
    if not terms:
        return {
            "status": "ok",
            "matches": [],
            "returnedCount": 0,
            "scope": {"ownerBound": True},
            "_queryBinding": {"mode": "empty-query", "queryKey": _query_key([])},
        }

    retry_after = _rpc_circuit_retry_after()
    if retry_after:
        raise HTTPException(
            status_code=503,
            detail="Project L owner-scoped retrieval is temporarily unavailable.",
            headers={"Retry-After": str(retry_after)},
        )

    probe_acquired = False
    if _rpc_requires_half_open_probe():
        probe_acquired = _rpc_half_open_probe.acquire(blocking=False)
        if not probe_acquired:
            raise HTTPException(
                status_code=503,
                detail="Project L owner-scoped retrieval recovery probe is already in progress.",
                headers={"Retry-After": "1"},
            )

    query_key = _query_key(terms)
    common_payload = {
        "p_user": owner_id,
        "p_terms": terms,
        "p_limit": min(max(int(limit), 1), 6),
        "p_char_budget": min(12000, max(2400, int(limit) * 1800)),
    }
    retry_index = 0

    acquired = _rpc_bulkhead.acquire(timeout=_RPC_BULKHEAD_WAIT_SECONDS)
    if not acquired:
        if probe_acquired:
            _rpc_half_open_probe.release()
        raise HTTPException(
            status_code=503,
            detail="Project L owner-scoped retrieval is temporarily saturated.",
            headers={"Retry-After": "1"},
        )

    try:
        while True:
            try:
                result = _database().rpc(
                    "project_l_memory_context_service_v2",
                    {**common_payload, "p_query_key": query_key},
                ).execute()
                break
            except Exception as exc:
                code = _rpc_error_code(exc)
                delays = _TRANSIENT_RPC_RETRY_DELAYS.get(code, ())
                if retry_index < len(delays):
                    delay = delays[retry_index]
                    retry_index += 1
                    if code in {"PGRST002", "PGRST003", "HTTP_TIMEOUT"}:
                        # Close the door to concurrent callers while this request
                        # performs its single bounded retry.
                        _open_rpc_circuit(_DATA_API_CIRCUIT_SECONDS)
                    print(
                        "SHINE_AI_MEMORY_RPC_RETRY "
                        f"code={code} attempt={retry_index} delay={delay:.2f}s",
                        flush=True,
                    )
                    time.sleep(delay)
                    continue

                if code in {"PGRST002", "PGRST003", "HTTP_TIMEOUT"}:
                    _escalate_rpc_circuit()

                print("SHINE_AI_MEMORY_RPC_ERROR " + _safe_rpc_error(exc), flush=True)
                response_retry_after = (
                    _rpc_circuit_retry_after()
                    if code in {"PGRST002", "PGRST003", "HTTP_TIMEOUT"}
                    else 1 if code == "57014"
                    else 0
                )
                raise HTTPException(
                    status_code=503,
                    detail="Project L owner-scoped retrieval is temporarily unavailable.",
                    headers=(
                        {"Retry-After": str(response_retry_after)}
                        if response_retry_after
                        else None
                    ),
                ) from exc
    finally:
        _rpc_bulkhead.release()
        if probe_acquired:
            _rpc_half_open_probe.release()

    data = result.data
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
        data = data[0]
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=503,
            detail="Project L owner-scoped retrieval returned an invalid payload.",
        )
    if str(data.get("queryKey") or "") != query_key:
        raise HTTPException(
            status_code=503,
            detail="Project L owner-scoped retrieval failed its query binding check.",
        )
    if str(data.get("queryContractVersion") or "") != _QUERY_CONTRACT_VERSION:
        raise HTTPException(
            status_code=503,
            detail="Project L owner-scoped retrieval failed its query contract check.",
        )
    if data.get("status") == "no_scope":
        raise HTTPException(
            status_code=503,
            detail="Project L owner-scoped retrieval has no active permission scope.",
        )
    _close_rpc_circuit()
    data = dict(data)
    data["_queryBinding"] = {
        "mode": "server-verified",
        "queryKey": query_key,
        "queryContractVersion": _QUERY_CONTRACT_VERSION,
    }
    return data


def _priority(item: dict) -> Priority:
    authority = item.get("authority") if isinstance(item.get("authority"), dict) else {}
    authority_class = str(authority.get("class") or "")
    if authority_class in {"user_confirmed_correction", "direct_user_promoted_memory"}:
        return "high"
    if authority_class == "assistant_derived_promoted_memory":
        return "low"
    return "normal"


def _records(
    context: dict,
    requested_scopes: frozenset[str],
    limit: int,
) -> list[MemoryRecordResponse]:
    rows = context.get("matches")
    if not isinstance(rows, list):
        raise HTTPException(
            status_code=503,
            detail="Project L owner-scoped retrieval returned invalid records.",
        )

    records: list[MemoryRecordResponse] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("domain") or "").strip().lower()
        if domain not in requested_scopes:
            continue

        text = str(item.get("content") or "").strip()
        provenance = (
            item.get("provenance")
            if isinstance(item.get("provenance"), dict)
            else {}
        )
        source_table = str(provenance.get("sourceTable") or "").strip()
        source_id = str(provenance.get("sourceId") or item.get("id") or "").strip()
        source_role = str(provenance.get("sourceRole") or "unknown").strip().lower()
        if not text or not source_table or not source_id:
            continue

        record_id = f"{source_table}:{source_id}"[:80]
        records.append(
            MemoryRecordResponse(
                id=record_id,
                text=text[:1800],
                tags=[domain, source_role or "unknown", "owner-scoped-v2"],
                priority=_priority(item),
            )
        )
        if len(records) >= limit:
            break
    return records


@router.get("/memory/health", response_model=MemoryBridgeHealthResponse)
def memory_bridge_health(
    x_shine_service_token: str = Header(default=""),
) -> MemoryBridgeHealthResponse:
    # Authenticate against the same narrow service credential as retrieval.
    # Deliberately do not touch Supabase: this endpoint must remain useful while
    # the database is the dependency that is failing.
    _configured_owner(x_shine_service_token)
    snapshot = _rpc_runtime_snapshot()
    return MemoryBridgeHealthResponse(
        source="project-l",
        component="memory-bridge",
        version="2.2",
        status=str(snapshot["status"]),
        circuit_state=str(snapshot["circuit_state"]),
        retry_after=int(snapshot["retry_after"]),
        failure_streak=int(snapshot["failure_streak"]),
        recovery_probe_in_progress=bool(
            snapshot["recovery_probe_in_progress"]
        ),
        database_configured=bool(snapshot["database_configured"]),
        database_touched=False,
        max_concurrent_rpcs=_MAX_CONCURRENT_MEMORY_RPCS,
        rpc_timeout_seconds=_MEMORY_RPC_TIMEOUT_SECONDS,
        rpc_connect_seconds=_MEMORY_RPC_CONNECT_SECONDS,
        rpc_pool_seconds=_MEMORY_RPC_POOL_SECONDS,
        read_only=True,
        fail_closed=True,
    )


@router.post("/memory/retrieve", response_model=MemoryRetrieveResponse)
def retrieve_memory(
    request: MemoryRetrieveRequest,
    x_shine_service_token: str = Header(default=""),
) -> MemoryRetrieveResponse:
    owner_id = _configured_owner(x_shine_service_token)
    requested_scopes = _validate_access(request, owner_id)
    context = _owner_context(owner_id, request.query, request.limit)
    records = _records(context, requested_scopes, request.limit)

    unavailable_scopes = sorted(
        scope for scope in requested_scopes
        if scope == "episodic"
    )
    scope_receipt = context.get("scope") if isinstance(context.get("scope"), dict) else {}
    compression = (
        context.get("compression")
        if isinstance(context.get("compression"), dict)
        else {}
    )

    query_binding = (
        context.get("_queryBinding")
        if isinstance(context.get("_queryBinding"), dict)
        else {}
    )

    return MemoryRetrieveResponse(
        source="project-l",
        engine="project-l-memory-context-v2",
        version="2.2",
        recall_active=bool(records),
        records=records,
        receipt={
            "status": str(context.get("status") or "unknown"),
            "requested_scopes": sorted(requested_scopes),
            "unavailable_scopes": unavailable_scopes,
            "records_returned": len(records),
            "owner_bound": scope_receipt.get("ownerBound") is True,
            "permission_scoped": True,
            "quarantine_excluded": scope_receipt.get("quarantineExcluded") is True,
            "corrections_preferred": scope_receipt.get("correctionsPreferred") is True,
            "compression": compression,
            "bounded": True,
            "read_only": True,
            "legacy_global_search_used": False,
            "legacy_rpc_fallback_used": False,
            "query_binding": str(query_binding.get("mode") or "unknown"),
            "query_key": str(query_binding.get("queryKey") or ""),
            "query_contract_version": str(
                query_binding.get("queryContractVersion") or ""
            ),
        },
    )
