"""Project L core operational readiness contract.

Readiness is intentionally separate from Railway liveness. A transient memory
failure should not trigger a restart loop, but operators still need a truthful
signal when the core recall path is not currently ready to serve.
"""

from __future__ import annotations

from typing import Any


READY_MEMORY_STATES = frozenset({"healthy", "recovered_observing"})
NONBLOCKING_MEMORY_STATES = frozenset({"warming"})
NOT_READY_MEMORY_STATES = frozenset({"recovering", "degraded"})


def _memory_component(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    runtime = snapshot.get("runtime")
    runtime = runtime if isinstance(runtime, dict) else {}

    operational_state = str(runtime.get("operational_state") or "unknown")
    recovery_state = str(runtime.get("recovery_state") or "unknown")
    historical_status = str(runtime.get("status") or "unknown")

    if operational_state in READY_MEMORY_STATES:
        readiness = "ready"
    elif operational_state in NONBLOCKING_MEMORY_STATES:
        readiness = "warming"
    else:
        readiness = "not_ready"

    return {
        "required": True,
        "readiness": readiness,
        "operational_state": operational_state,
        "recovery_state": recovery_state,
        "historical_slo_status": historical_status,
        "samples": int(runtime.get("samples", 0) or 0),
        "qualified_recovery_successes": int(
            runtime.get("qualified_recovery_successes", 0) or 0
        ),
    }


def _memory_process_component(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    status = str(snapshot.get("status") or "unknown")
    circuit_state = str(snapshot.get("circuit_state") or "unknown")
    database_configured = bool(snapshot.get("database_configured"))
    process_ready = (
        status == "ready"
        and circuit_state == "closed"
        and database_configured
    )
    return {
        "required": True,
        "ready": process_ready,
        "status": status,
        "circuit_state": circuit_state,
        "retry_after": int(snapshot.get("retry_after", 0) or 0),
        "failure_streak": int(snapshot.get("failure_streak", 0) or 0),
        "recovery_probe_in_progress": bool(
            snapshot.get("recovery_probe_in_progress")
        ),
        "database_configured": database_configured,
    }


def _foundation_component(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    status = str(snapshot.get("status") or "unknown")
    return {
        "required": False,
        "status": status,
        "attempts": int(snapshot.get("attempts", 0) or 0),
        "background_retry": bool(snapshot.get("background_retry")),
        "retry_exhausted": bool(snapshot.get("retry_exhausted")),
    }


def _security_component(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    enforced = bool(snapshot.get("production_enforced"))
    ready = bool(snapshot.get("ready"))
    return {
        "required": True,
        "production_enforced": enforced,
        "ready": ready,
    }


def build_operational_readiness(
    *,
    security_gate: dict[str, Any] | None,
    memory_snapshot: dict[str, Any] | None,
    memory_process_snapshot: dict[str, Any] | None,
    foundation_snapshot: dict[str, Any] | None,
) -> tuple[dict[str, Any], int]:
    """Return a privacy-safe readiness payload and HTTP status code.

    Rules:
    - production security remains fail closed;
    - current-process memory circuit/configuration and durable memory are core readiness dependencies;
    - Foundation authority is visible but optional to standalone Project L;
    - historical SLO misses do not override a current recovered-observing state;
    - warming memory remains ready enough to serve while evidence accumulates.
    """

    security = _security_component(security_gate)
    memory = _memory_component(memory_snapshot)
    memory_process = _memory_process_component(memory_process_snapshot)
    foundation = _foundation_component(foundation_snapshot)

    if security["production_enforced"] and not security["ready"]:
        status = "blocked"
        http_status = 503
        reason = "production-security-gate"
    elif not memory_process["ready"]:
        status = "degraded"
        http_status = 503
        reason = "memory-process-not-ready"
    elif memory["readiness"] == "not_ready":
        status = "degraded"
        http_status = 503
        reason = "memory-runtime-not-ready"
    elif memory["readiness"] == "warming":
        status = "warming"
        http_status = 200
        reason = "memory-runtime-warming"
    else:
        status = "ready"
        http_status = 200
        reason = "core-operational"

    payload = {
        "status": status,
        "reason": reason,
        "components": {
            "production_security": security,
            "memory_process": memory_process,
            "memory_runtime": memory,
            "foundation_authority": foundation,
        },
    }
    return payload, http_status
