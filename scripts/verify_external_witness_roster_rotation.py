"""Deployment smoke for external witness roster storage-key rotation."""

import os

from supabase import create_client

from services.external_witness_roster import (
    CERTIFIED_GENESIS_ROSTER_SHA256,
    load_persisted_external_witness_roster,
)


def _database():
    url = os.getenv("SUPABASE_URL", "").strip()
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
    )
    if not url or not key:
        raise SystemExit(
            "Project L external roster rotation smoke: FAIL database-unavailable"
        )
    return create_client(url, key)


def main() -> None:
    target = os.getenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_ROTATION_TARGET_KEY_ID",
        "",
    ).strip()
    if not target:
        raise SystemExit(
            "Project L external roster rotation smoke: FAIL target-unavailable"
        )

    db = _database()
    first = load_persisted_external_witness_roster(db)
    second = load_persisted_external_witness_roster(db)

    if (
        first.get("generation") != 1
        or first.get("policySha256") != CERTIFIED_GENESIS_ROSTER_SHA256
        or first.get("roster_storage_auth_key_id") != target
        or first.get("roster_storage_authenticated") is not True
        or first.get("roster_storage_checkpoint_independent") is not True
        or second.get("roster_storage_auth_key_id") != target
        or second.get("roster_storage_rotation_mode") != "not-needed"
        or first.get("roster_storage_state_sha256")
            != second.get("roster_storage_state_sha256")
    ):
        raise SystemExit(
            "Project L external roster rotation smoke: FAIL verification"
        )

    print(
        "Project L external roster rotation smoke: PASS "
        f"generation={first.get('generation')} "
        f"target={target} "
        "state=preserved checkpoint=railway-redis-volume"
    )


if __name__ == "__main__":
    main()
