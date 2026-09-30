"""Production pre-deploy smoke for Project L's owner-bound memory bridge.

Runs entirely inside the deployment image so Railway secrets stay private.
The smoke exercises the authenticated FastAPI route and live Supabase v2 RPC,
but never prints memory content, owner identifiers, or service credentials.
"""

import os

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import shine_ai_memory as bridge


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


def main() -> None:
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

    print(
        "Project L memory bridge live smoke: PASS "
        f"circuit={after.get('circuit_state')} "
        f"records={receipt.get('records_returned')} "
        f"owner_bound={str(receipt.get('owner_bound')).lower()} "
        f"query_binding={receipt.get('query_binding')} "
        f"contract={receipt.get('query_contract_version')} "
        f"requests={after_metrics.get('requests_total')} "
        f"success_rate={after_metrics.get('success_rate')} "
        f"latency_ms={after_metrics.get('last_latency_ms')}"
    )


if __name__ == "__main__":
    main()
