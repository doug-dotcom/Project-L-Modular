"""Read-only production smoke for Shine Me owner-account state continuity.

This smoke validates the live Supabase table and owner-binding configuration.
It never prints owner IDs, journal text, dashboard content, or row identifiers.
"""

from __future__ import annotations

import json
import os

from supabase import create_client


def _fail(reason: str) -> None:
    raise SystemExit(f"Project L Shine-Me state sync smoke: FAIL {reason}")


def _client():
    url = str(os.getenv("SUPABASE_URL") or "").strip()
    key = str(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key:
        _fail("database-config-missing")
    return create_client(url, key)


def main() -> None:
    owner_id = str(os.getenv("PROJECT_L_OWNER_ID") or "").strip()
    memory_owner_id = str(os.getenv("L_MEMORY_OWNER_ID") or "").strip()
    if not owner_id or not memory_owner_id:
        _fail("owner-binding-config-missing")
    if owner_id != memory_owner_id:
        _fail("owner-binding-mismatch")

    try:
        result = (
            _client()
            .table("shine_me_owner_state")
            .select("owner_id,state,revision,updated_at")
            .eq("owner_id", owner_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        _fail(type(exc).__name__.lower()[:80] or "query-failed")

    rows = getattr(result, "data", None)
    if not isinstance(rows, list):
        _fail("result-invalid")
    if len(rows) > 1:
        _fail("owner-row-nonunique")

    status = "empty"
    revision = 0
    state_bytes = 0
    if rows:
        row = rows[0]
        if not isinstance(row, dict):
            _fail("row-invalid")
        if str(row.get("owner_id") or "") != owner_id:
            _fail("owner-row-mismatch")
        state = row.get("state")
        revision = row.get("revision")
        updated_at = row.get("updated_at")
        if not isinstance(state, dict):
            _fail("state-invalid")
        if not isinstance(revision, int) or revision < 1:
            _fail("revision-invalid")
        if not isinstance(updated_at, str) or not updated_at.strip():
            _fail("updated-at-invalid")
        state_bytes = len(json.dumps(state, separators=(",", ":"), ensure_ascii=False).encode())
        if state_bytes > 262_144:
            _fail("state-oversize")
        status = "present"

    try:
        health_result = (
            _client()
            .rpc(
                "shine_me_owner_state_conflict_health_service_v1",
                {"p_owner_id": owner_id},
            )
            .execute()
        )
    except Exception as exc:
        _fail("conflict-health-" + (type(exc).__name__.lower()[:60] or "query-failed"))

    health_rows = getattr(health_result, "data", None)
    if not isinstance(health_rows, list) or len(health_rows) != 1:
        _fail("conflict-health-result-invalid")
    health = health_rows[0]
    if not isinstance(health, dict):
        _fail("conflict-health-row-invalid")
    health_status = str(health.get("health_status") or "")
    if health_status not in {"stable", "isolated", "recurring", "persistent"}:
        _fail("conflict-health-status-invalid")
    detections_24h = health.get("detections_24h")
    unresolved = health.get("unresolved_conflicts")
    oldest_minutes = health.get("oldest_unresolved_minutes")
    for name, value in (
        ("detections", detections_24h),
        ("unresolved", unresolved),
        ("oldest", oldest_minutes),
    ):
        if not isinstance(value, int) or value < 0:
            _fail("conflict-health-" + name + "-invalid")

    print(
        "Project L Shine-Me state sync smoke: PASS "
        f"binding=server-verified state={status} revision={revision} "
        f"state_bytes={state_bytes} direct_browser_access=blocked-by-contract "
        f"conflict_health={health_status} detections_24h={detections_24h} "
        f"unresolved={unresolved} oldest_unresolved_minutes={oldest_minutes}"
    )


if __name__ == "__main__":
    main()
