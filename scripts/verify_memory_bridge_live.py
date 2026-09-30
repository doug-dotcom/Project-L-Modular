"""Production pre-deploy smoke for Project L's owner-bound memory bridge.

Runs entirely inside the deployment image so Railway secrets stay private.
The smoke exercises the authenticated FastAPI route and live Supabase v2 RPC,
but never prints memory content, owner identifiers, or service credentials.
"""

import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import shine_ai_memory as bridge
from orchestration.lieutenants.observability_lieutenant import (
    OBSERVABILITY_LIEUTENANT,
)


def _required_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise SystemExit(
        "Project L memory bridge live smoke: FAIL required-environment-unavailable"
    )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(bridge.router)
    return TestClient(app)


def _health(client: TestClient, token: str) -> dict:
    response = client.get(
        "/internal/shine-ai/memory/health",
        headers={"X-Shine-Service-Token": token},
    )
    if response.status_code != 200:
        raise SystemExit(
            "Project L memory bridge live smoke: FAIL health-unavailable"
        )
    body = response.json()
    if (
        body.get("source") != "project-l"
        or body.get("component") != "memory-bridge"
        or body.get("status") != "ready"
        or body.get("circuit_state") != "closed"
        or body.get("database_configured") is not True
        or body.get("database_touched") is not False
        or body.get("fail_closed") is not True
    ):
        raise SystemExit(
            "Project L memory bridge live smoke: FAIL health-contract-invalid"
        )
    return body


def _retrieve(client: TestClient, token: str, owner_id: str) -> dict:
    response = client.post(
        "/internal/shine-ai/memory/retrieve",
        headers={"X-Shine-Service-Token": token},
        json={
            "app": "shine-dive",
            "user_id": owner_id,
            "query": "diving bali",
            "scopes": ["sport"],
            "limit": 4,
        },
    )
    if response.status_code != 200:
        raise SystemExit(
            "Project L memory bridge live smoke: FAIL retrieval-unavailable"
        )

    body = response.json()
    receipt = body.get("receipt") if isinstance(body.get("receipt"), dict) else {}
    records = body.get("records") if isinstance(body.get("records"), list) else []

    if (
        body.get("source") != "project-l"
        or body.get("engine") != "project-l-memory-context-v2"
        or body.get("version") != "2.2"
        or body.get("recall_active") is not True
        or receipt.get("status") != "ok"
        or receipt.get("owner_bound") is not True
        or receipt.get("permission_scoped") is not True
        or receipt.get("bounded") is not True
        or receipt.get("read_only") is not True
        or receipt.get("legacy_global_search_used") is not False
        or receipt.get("legacy_rpc_fallback_used") is not False
        or receipt.get("query_binding") != "server-verified"
        or str(receipt.get("query_contract_version") or "") != "2"
        or len(str(receipt.get("query_key") or "")) != 32
        or int(receipt.get("records_returned") or 0) != len(records)
        or len(records) < 1
    ):
        raise SystemExit(
            "Project L memory bridge live smoke: FAIL retrieval-contract-invalid"
        )
    return body


SLO_MIN_SAMPLES = 20
SLO_AVAILABILITY_TARGET = 0.99
SLO_EWMA_LATENCY_TARGET_MS = 3000.0
SLO_HISTORY_LIMIT = 100


def _failure_stage(exc: BaseException) -> str:
    if isinstance(exc, SystemExit):
        message = str(exc)
        prefix = "Project L memory bridge live smoke: FAIL "
        if message.startswith(prefix):
            candidate = message[len(prefix):].strip().lower()
            if candidate and all(
                ch.isalnum() or ch in {"-", "_"} for ch in candidate
            ):
                return candidate[:80]
    return type(exc).__name__.lower()[:80] or "unknown"


def _record_history(payload: dict) -> dict:
    try:
        return OBSERVABILITY_LIEUTENANT.record_event(
            "memory_bridge_deploy_slo",
            payload,
        )
    except Exception:
        return {
            "recorded": False,
            "event_type": "memory_bridge_deploy_slo",
            "storage": "none",
        }


def _durable_slo_summary() -> dict:
    try:
        events = OBSERVABILITY_LIEUTENANT.load_events()
    except Exception:
        events = []

    relevant = [
        item
        for item in events
        if isinstance(item, dict)
        and item.get("event_type") == "memory_bridge_deploy_slo"
        and isinstance(item.get("payload"), dict)
    ][-SLO_HISTORY_LIMIT:]

    success_count = 0
    failure_count = 0
    ewma_latency_ms = 0.0
    latency_samples = 0

    for item in relevant:
        payload = item["payload"]
        outcome = str(payload.get("outcome") or "success").strip().lower()
        if outcome == "success":
            success_count += 1
            try:
                latency_ms = float(payload.get("latency_ms"))
            except (TypeError, ValueError):
                latency_ms = -1.0
            if latency_ms >= 0:
                ewma_latency_ms = (
                    latency_ms
                    if latency_samples == 0
                    else ewma_latency_ms * 0.8 + latency_ms * 0.2
                )
                latency_samples += 1
        else:
            failure_count += 1

    samples = success_count + failure_count
    availability = success_count / samples if samples else None

    if samples < SLO_MIN_SAMPLES:
        status = "warming"
    elif (
        availability is not None
        and availability >= SLO_AVAILABILITY_TARGET
        and latency_samples > 0
        and ewma_latency_ms <= SLO_EWMA_LATENCY_TARGET_MS
    ):
        status = "met"
    else:
        status = "missed"

    return {
        "status": status,
        "samples": samples,
        "successes": success_count,
        "failures": failure_count,
        "availability": (
            round(availability, 6) if availability is not None else None
        ),
        "ewma_latency_ms": (
            round(ewma_latency_ms, 1) if latency_samples else None
        ),
        "history_limit": SLO_HISTORY_LIMIT,
        "min_samples": SLO_MIN_SAMPLES,
        "availability_target": SLO_AVAILABILITY_TARGET,
        "ewma_latency_target_ms": SLO_EWMA_LATENCY_TARGET_MS,
    }


def _durable_runtime_slo_summary() -> dict:
    try:
        events = OBSERVABILITY_LIEUTENANT.load_events()
    except Exception:
        events = []

    rollups = [
        item
        for item in events
        if isinstance(item, dict)
        and item.get("event_type") == "memory_bridge_runtime_rollup"
        and isinstance(item.get("payload"), dict)
    ][-SLO_HISTORY_LIMIT:]

    runtime = [
        item["payload"]
        for item in rollups
        if str(item["payload"].get("rollup_kind") or "")
        in {"periodic", "shutdown"}
    ]
    periodic_rollups = sum(
        1
        for item in rollups
        if str(item["payload"].get("rollup_kind") or "") == "periodic"
    )
    shutdown_rollups = sum(
        1
        for item in rollups
        if str(item["payload"].get("rollup_kind") or "") == "shutdown"
    )
    canary_rollups = sum(
        1
        for item in rollups
        if str(item["payload"].get("rollup_kind") or "") == "canary"
    )

    successes = sum(int(item.get("successes", 0) or 0) for item in runtime)
    failures = sum(int(item.get("failures", 0) or 0) for item in runtime)
    completed = successes + failures

    latency_sum_ms = 0.0
    latency_completed = 0
    for item in runtime:
        item_completed = (
            int(item.get("successes", 0) or 0)
            + int(item.get("failures", 0) or 0)
        )
        try:
            mean_latency_ms = float(item.get("mean_latency_ms"))
        except (TypeError, ValueError):
            mean_latency_ms = -1.0
        if item_completed > 0 and mean_latency_ms >= 0:
            latency_sum_ms += mean_latency_ms * item_completed
            latency_completed += item_completed

    availability = successes / completed if completed else None
    mean_latency_ms = (
        latency_sum_ms / latency_completed if latency_completed else None
    )

    if completed < SLO_MIN_SAMPLES:
        status = "warming"
    elif (
        availability is not None
        and availability >= SLO_AVAILABILITY_TARGET
        and mean_latency_ms is not None
        and mean_latency_ms <= SLO_EWMA_LATENCY_TARGET_MS
    ):
        status = "met"
    else:
        status = "missed"

    return {
        "status": status,
        "samples": completed,
        "successes": successes,
        "failures": failures,
        "availability": (
            round(availability, 6) if availability is not None else None
        ),
        "mean_latency_ms": (
            round(mean_latency_ms, 1) if mean_latency_ms is not None else None
        ),
        "rollup_events": len(rollups),
        "periodic_rollups": periodic_rollups,
        "shutdown_rollups": shutdown_rollups,
        "canary_rollups": canary_rollups,
    }


def _run_success_path() -> tuple[dict, dict, dict, dict]:
    token = _required_env("SHINE_AI_MEMORY_TOKEN")
    owner_id = _required_env("L_MEMORY_OWNER_ID", "PROJECT_L_OWNER_ID")

    client = _client()
    before = _health(client, token)
    before_metrics = (
        before.get("metrics")
        if isinstance(before.get("metrics"), dict)
        else {}
    )
    result = _retrieve(client, token, owner_id)
    receipt = result["receipt"]
    after = _health(client, token)
    after_metrics = (
        after.get("metrics")
        if isinstance(after.get("metrics"), dict)
        else {}
    )

    if (
        int(after_metrics.get("requests_total") or 0)
            < int(before_metrics.get("requests_total") or 0) + 1
        or int(after_metrics.get("success_total") or 0)
            < int(before_metrics.get("success_total") or 0) + 1
        or int(after_metrics.get("failure_total") or 0)
            < int(before_metrics.get("failure_total") or 0)
        or after_metrics.get("success_rate") is None
        or float(after_metrics.get("last_latency_ms") or -1) < 0
    ):
        raise SystemExit(
            "Project L memory bridge live smoke: FAIL telemetry-unverified"
        )

    runtime_rollup = bridge._flush_runtime_rollup(
        force=True,
        synchronous=True,
        rollup_kind="canary",
    )
    if (
        runtime_rollup.get("scheduled") is not True
        or runtime_rollup.get("recorded") is not True
        or runtime_rollup.get("storage") != "railway-redis-volume"
    ):
        raise SystemExit(
            "Project L memory bridge live smoke: FAIL runtime-rollup-unavailable"
        )

    return after, after_metrics, receipt, runtime_rollup


def main() -> None:
    try:
        after, after_metrics, receipt, runtime_rollup = _run_success_path()
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, GeneratorExit)):
            raise

        history = _record_history(
            {
                "outcome": "failure",
                "failure_stage": _failure_stage(exc),
                "records": 0,
                "success_rate": 0.0,
            }
        )
        durable = _durable_slo_summary()
        print(
            "Project L memory bridge live smoke history: RECORDED "
            f"outcome=failure "
            f"history={history.get('storage')} "
            f"durable_slo={durable.get('status')} "
            f"durable_samples={durable.get('samples')} "
            f"durable_availability={durable.get('availability')}"
        )
        if isinstance(exc, SystemExit):
            raise
        raise SystemExit(
            "Project L memory bridge live smoke: FAIL unexpected-error"
        ) from exc

    history = _record_history(
        {
            "outcome": "success",
            "circuit_state": after.get("circuit_state"),
            "records": receipt.get("records_returned"),
            "contract_version": receipt.get("query_contract_version"),
            "telemetry_requests": after_metrics.get("requests_total"),
            "success_rate": after_metrics.get("success_rate"),
            "latency_ms": after_metrics.get("last_latency_ms"),
            "slo_status": after_metrics.get("slo_status"),
        }
    )
    durable = _durable_slo_summary()
    runtime_durable = _durable_runtime_slo_summary()

    print(
        "Project L memory bridge live smoke: PASS "
        f"circuit={after.get('circuit_state')} "
        f"records={receipt.get('records_returned')} "
        f"owner_bound={str(receipt.get('owner_bound')).lower()} "
        f"query_binding={receipt.get('query_binding')} "
        f"contract={receipt.get('query_contract_version')} "
        f"requests={after_metrics.get('requests_total')} "
        f"success_rate={after_metrics.get('success_rate')} "
        f"latency_ms={after_metrics.get('last_latency_ms')} "
        f"slo={after_metrics.get('slo_status')} "
        f"history={history.get('storage')} "
        f"durable_slo={durable.get('status')} "
        f"durable_samples={durable.get('samples')} "
        f"durable_successes={durable.get('successes')} "
        f"durable_failures={durable.get('failures')} "
        f"durable_availability={durable.get('availability')} "
        f"durable_ewma_latency_ms={durable.get('ewma_latency_ms')} "
        f"runtime_rollup={runtime_rollup.get('storage')} "
        f"runtime_slo={runtime_durable.get('status')} "
        f"runtime_samples={runtime_durable.get('samples')} "
        f"runtime_successes={runtime_durable.get('successes')} "
        f"runtime_failures={runtime_durable.get('failures')} "
        f"runtime_availability={runtime_durable.get('availability')} "
        f"runtime_mean_latency_ms={runtime_durable.get('mean_latency_ms')} "
        f"runtime_periodic_rollups={runtime_durable.get('periodic_rollups')} "
        f"runtime_shutdown_rollups={runtime_durable.get('shutdown_rollups')} "
        f"runtime_canary_rollups={runtime_durable.get('canary_rollups')}"
    )


if __name__ == "__main__":
    main()
