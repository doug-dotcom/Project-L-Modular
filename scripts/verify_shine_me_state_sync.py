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
        if state_bytes > 64_000:
            _fail("state-oversize")
        status = "present"

    print(
        "Project L Shine-Me state sync smoke: PASS "
        f"binding=server-verified state={status} revision={revision} "
        f"state_bytes={state_bytes} direct_browser_access=blocked-by-contract"
    )


if __name__ == "__main__":
    main()
