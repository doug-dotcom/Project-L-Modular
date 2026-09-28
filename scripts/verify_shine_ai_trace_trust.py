"""Deployment smoke for Project L's durable Shine-AI trace trust surface."""

import os

from supabase import create_client

from services import shine_runtime_service as runtime


def _database():
    url = os.getenv("SUPABASE_URL", "").strip()
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
    )
    if not url or not key:
        raise SystemExit(
            "Project L Shine-AI trace trust smoke: FAIL database-unavailable"
        )
    return create_client(url, key)


def main() -> None:
    runtime._TRACE_KEYSET_CACHE.update({
        "expires_at": 0.0,
        "pin": "",
        "keyset": None,
        "trust": None,
    })
    keyset, error, trust = runtime._shine_ai_verification_keyset(
        _database()
    )
    if (
        error is not None
        or not isinstance(keyset, dict)
        or not isinstance(trust, dict)
        or trust.get("status") != "trusted"
        or trust.get("anti_rollback") is not True
        or trust.get("persisted_state_valid") is not True
    ):
        raise SystemExit(
            "Project L Shine-AI trace trust smoke: FAIL "
            + str(error or trust.get("reason_code") or "keyset-unavailable")
        )
    print(
        "Project L Shine-AI trace trust smoke: PASS "
        f"generation={keyset.get('generation')} "
        f"keys={len(keyset.get('verification_keys') or {})} "
        f"mode={trust.get('acceptance_mode')} "
        "anti_rollback=on"
    )


if __name__ == "__main__":
    main()
