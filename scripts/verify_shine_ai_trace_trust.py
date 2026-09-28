"""Deployment smoke for Project L's authenticated Shine-AI trust storage."""

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


def _reset_cache() -> None:
    runtime._TRACE_KEYSET_CACHE.update({
        "expires_at": 0.0,
        "pin": "",
        "keyset": None,
        "trust": None,
    })


def main() -> None:
    db = _database()
    _reset_cache()

    sealed, seal_error = runtime._seal_existing_trace_trust_state(db)
    if seal_error is not None or not isinstance(sealed, dict):
        raise SystemExit(
            "Project L Shine-AI trace trust smoke: FAIL "
            + str(seal_error or "trust-storage-seal-failed")
        )

    _reset_cache()
    keyset, error, trust = runtime._shine_ai_verification_keyset(db)
    if (
        error is not None
        or not isinstance(keyset, dict)
        or not isinstance(trust, dict)
        or trust.get("status") != "trusted"
        or trust.get("storage_authenticated") is not True
        or trust.get("checkpoint_independent") is not True
    ):
        raise SystemExit(
            "Project L Shine-AI trace trust smoke: FAIL "
            + str(error or trust.get("reason_code") or "keyset-unavailable")
        )

    quorum = (
        trust.get("witness_quorum")
        if isinstance(trust.get("witness_quorum"), dict)
        else {}
    )
    if (
        quorum.get("status") != "verified"
        or int(quorum.get("minimum_witnesses") or 0) != 2
        or int(quorum.get("verified_witness_count") or 0) != 2
        or quorum.get("witness_ids")
        != ["foundation-project-l", "redis-project-l"]
    ):
        raise SystemExit(
            "Project L Shine-AI trace trust smoke: FAIL "
            "witness-quorum-unverified"
        )

    chain = (
        quorum.get("foundation_chain")
        if isinstance(quorum.get("foundation_chain"), dict)
        else {}
    )
    chain_tag = chain.get("chain_tag")
    if (
        chain.get("status") != "verified"
        or chain.get("witness_id") != "foundation-project-l"
        or chain.get("chain_version") != 1
        or chain.get("sequence") != quorum.get("sequence")
        or not isinstance(chain_tag, str)
        or len(chain_tag) != 64
        or any(ch not in "0123456789abcdef" for ch in chain_tag)
    ):
        raise SystemExit(
            "Project L Shine-AI trace trust smoke: FAIL "
            "foundation-chain-unverified"
        )

    storage = sealed.get("storage") if isinstance(sealed.get("storage"), dict) else {}
    print(
        "Project L Shine-AI trace trust smoke: PASS "
        f"generation={keyset.get('generation')} "
        f"keys={len(keyset.get('verification_keys') or {})} "
        f"mode={trust.get('acceptance_mode')} "
        f"storage=authenticated "
        f"checkpoint={storage.get('independent_retention')} "
        f"quorum={quorum.get('verified_witness_count')}/"
        f"{quorum.get('minimum_witnesses')} "
        f"policy=persisted-g{quorum.get('policy_trust_generation')} "
        f"foundation_chain=verified"
    )


if __name__ == "__main__":
    main()
