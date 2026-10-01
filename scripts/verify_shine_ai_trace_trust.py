"""Deployment smoke for Project L's authenticated Shine-AI trust storage."""

import os
import time

import httpx
from supabase import create_client
from supabase.lib.client_options import SyncClientOptions

from services import shine_runtime_service as runtime

SMOKE_DB_TIMEOUT_SECONDS = 5.0
TRACE_SNAPSHOT_TRANSIENT_REASON = "trace-trust-snapshot-unavailable"
TRACE_SNAPSHOT_RETRY_DELAYS_SECONDS = (2.0, 5.0)


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
    transport = httpx.Client(
        http2=False,
        timeout=httpx.Timeout(
            SMOKE_DB_TIMEOUT_SECONDS,
            connect=3.0,
            pool=3.0,
        ),
        limits=httpx.Limits(
            max_connections=2,
            max_keepalive_connections=1,
            keepalive_expiry=2.0,
        ),
    )
    return create_client(
        url,
        key,
        options=SyncClientOptions(
            httpx_client=transport,
            auto_refresh_token=False,
            persist_session=False,
        ),
    )


def _reset_cache() -> None:
    runtime._TRACE_KEYSET_CACHE.update({
        "expires_at": 0.0,
        "pin": "",
        "keyset": None,
        "trust": None,
    })


def _seal_with_snapshot_recovery(db):
    sealed, error = runtime._seal_existing_trace_trust_state(db)
    replays = 0
    for delay in TRACE_SNAPSHOT_RETRY_DELAYS_SECONDS:
        if error != TRACE_SNAPSHOT_TRANSIENT_REASON:
            break
        replays += 1
        print(
            "Project L Shine-AI trace trust smoke: RETRY "
            f"snapshot_unavailable attempt={replays} "
            f"delay_seconds={delay:.1f}",
            flush=True,
        )
        time.sleep(delay)
        _reset_cache()
        sealed, error = runtime._seal_existing_trace_trust_state(db)
    return sealed, error, replays


def _keyset_with_snapshot_recovery(db):
    keyset, error, trust, keyset_replays = _keyset_with_snapshot_recovery(db)
    replays = 0
    for delay in TRACE_SNAPSHOT_RETRY_DELAYS_SECONDS:
        if error != TRACE_SNAPSHOT_TRANSIENT_REASON:
            break
        replays += 1
        print(
            "Project L Shine-AI trace trust smoke: RETRY "
            f"snapshot_unavailable attempt={replays} "
            f"delay_seconds={delay:.1f}",
            flush=True,
        )
        time.sleep(delay)
        _reset_cache()
        keyset, error, trust = runtime._shine_ai_verification_keyset(db)
    return keyset, error, trust, replays


def main() -> None:
    db = _database()
    _reset_cache()

    sealed, seal_error, seal_replays = _seal_with_snapshot_recovery(db)
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
        or quorum.get("policy_storage_authenticated") is not True
        or quorum.get("policy_storage_checkpoint_independent") is not True
        or not quorum.get("policy_storage_auth_key_id")
        or not quorum.get("policy_storage_state_sha256")
        or int(quorum.get("external_roster_generation") or 0) != 1
        or quorum.get("external_roster_policy_sha256")
            != "a5c456d49e47f1be3f2a7b7ed017328844484ba05c4e6ef3212412c6361156c4"
        or int(quorum.get("external_roster_minimum_witnesses") or 0) != 2
        or quorum.get("external_roster_witness_ids")
            != ["foundation-project-l", "redis-project-l"]
        or quorum.get("external_roster_trust_persisted") is not True
        or quorum.get("external_roster_storage_authenticated") is not True
        or quorum.get("external_roster_storage_checkpoint_independent")
            is not True
        or not quorum.get("external_roster_storage_auth_key_id")
        or not quorum.get("external_roster_storage_state_sha256")
        or quorum.get("external_roster_transition_evidence_status")
            != "not-applicable"
        or int(
            quorum.get("external_roster_transition_evidence_generation")
            or 0
        ) != 1
        or quorum.get(
            "external_roster_transition_evidence_chain_status"
        ) != "empty"
        or int(
            quorum.get("external_roster_transition_evidence_chain_version")
            or 0
        ) != 1
        or quorum.get(
            "external_roster_transition_evidence_chain_rows"
        ) != 0
        or int(
            quorum.get(
                "external_roster_transition_evidence_chain_generation"
            )
            or 0
        ) != 1
        or quorum.get("external_roster_transition_evidence_chain_tag")
            is not None
        or quorum.get("external_roster_head_verified") is not True
        or int(quorum.get("external_roster_head_sequence") or 0) != 1
        or int(quorum.get("external_roster_head_generation") or 0) != 1
        or not quorum.get("external_roster_head_checkpoint_sha256")
        or not quorum.get("external_roster_head_sha256")
        or quorum.get("external_roster_head_policy_sha256")
            != quorum.get("external_roster_policy_sha256")
        or quorum.get("external_roster_head_state_sha256")
            != quorum.get("external_roster_storage_state_sha256")
        or quorum.get("external_roster_head_witness_verified") is not True
        or quorum.get("external_roster_head_witness_id")
            != "foundation-project-l-roster-head"
        or not quorum.get("external_roster_head_witness_auth_key_id")
        or quorum.get(
            "external_roster_head_witness_independent_retention"
        ) != "foundation-supabase-vault-hmac"
    ):
        raise SystemExit(
            "Project L Shine-AI trace trust smoke: FAIL "
            "witness-quorum-unverified"
        )

    witness_rotation_target = os.getenv(
        "SHINE_TRACE_EXTERNAL_ROSTER_HEAD_WITNESS_ROTATION_TARGET_KEY_ID",
        "",
    ).strip()
    witness_rotation = (
        quorum.get("external_roster_head_witness_rotation")
        if isinstance(
            quorum.get("external_roster_head_witness_rotation"),
            dict,
        )
        else {}
    )
    if (
        quorum.get("external_roster_head_witness_rotation_supported")
        is not True
        or not witness_rotation
        or witness_rotation.get("status") != "verified"
        or witness_rotation.get("state_preserved") is not True
        or (
            witness_rotation_target
            and (
                quorum.get(
                    "external_roster_head_witness_auth_key_id"
                ) != witness_rotation_target
                or witness_rotation.get("target_auth_key_id")
                    != witness_rotation_target
            )
        )
    ):
        raise SystemExit(
            "Project L Shine-AI trace trust smoke: FAIL "
            "roster-head-witness-rotation-unverified"
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

    chain_checkpoint = (
        quorum.get("foundation_chain_checkpoint")
        if isinstance(
            quorum.get("foundation_chain_checkpoint"),
            dict,
        )
        else {}
    )
    if (
        chain_checkpoint.get("status") != "verified"
        or chain_checkpoint.get("checkpoint_version") != 1
        or chain_checkpoint.get("witness_id") != "foundation-project-l"
        or chain_checkpoint.get("chain_version") != 1
        or chain_checkpoint.get("sequence") != chain.get("sequence")
        or chain_checkpoint.get("chain_tag") != chain.get("chain_tag")
        or chain_checkpoint.get("previous_chain_tag")
            != chain.get("previous_chain_tag")
        or chain_checkpoint.get("storage")
            != "project-l-supabase-vault-hmac"
    ):
        raise SystemExit(
            "Project L Shine-AI trace trust smoke: FAIL "
            "foundation-chain-checkpoint-unverified"
        )

    redis_chain_checkpoint = (
        quorum.get("foundation_chain_redis_checkpoint")
        if isinstance(
            quorum.get("foundation_chain_redis_checkpoint"),
            dict,
        )
        else {}
    )
    redundancy = (
        quorum.get("foundation_chain_checkpoint_redundancy")
        if isinstance(
            quorum.get("foundation_chain_checkpoint_redundancy"),
            dict,
        )
        else {}
    )
    if (
        redis_chain_checkpoint.get("status") != "verified"
        or redis_chain_checkpoint.get("checkpoint_version") != 1
        or redis_chain_checkpoint.get("witness_id")
            != "foundation-project-l"
        or redis_chain_checkpoint.get("chain_version") != 1
        or redis_chain_checkpoint.get("sequence") != chain.get("sequence")
        or redis_chain_checkpoint.get("chain_tag") != chain.get("chain_tag")
        or redis_chain_checkpoint.get("previous_chain_tag")
            != chain.get("previous_chain_tag")
        or redis_chain_checkpoint.get("storage")
            != "railway-redis-volume"
        or redundancy.get("status") != "verified"
        or int(redundancy.get("verified_store_count") or 0) != 2
        or redundancy.get("sequence") != chain.get("sequence")
        or redundancy.get("chain_tag") != chain.get("chain_tag")
        or redundancy.get("previous_chain_tag")
            != chain.get("previous_chain_tag")
        or redundancy.get("stores") != [
            "project-l-supabase-vault-hmac",
            "railway-redis-volume",
        ]
    ):
        raise SystemExit(
            "Project L Shine-AI trace trust smoke: FAIL "
            "foundation-chain-checkpoint-redundancy-unverified"
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
        f"policy_storage={quorum.get('policy_storage_auth_key_id')} "
        f"policy_checkpoint={quorum.get('policy_storage_checkpoint_retention')} "
        f"roster=persisted-g{quorum.get('external_roster_generation')} "
        f"roster_storage={quorum.get('external_roster_storage_auth_key_id')} "
        f"roster_checkpoint={quorum.get('external_roster_storage_checkpoint_retention')} "
        f"roster_evidence_chain={quorum.get('external_roster_transition_evidence_chain_status')}-g"
        f"{quorum.get('external_roster_transition_evidence_chain_generation')} "
        f"roster_head_witness={quorum.get('external_roster_head_witness_id')} "
        f"roster_head_witness_key={quorum.get('external_roster_head_witness_auth_key_id')} "
        f"roster_head_witness_rotation={witness_rotation.get('mode')} "
        f"foundation_chain=verified "
        f"chain_checkpoint=verified "
        f"chain_checkpoint_redundancy=2/2 "
        f"snapshot_replays={seal_replays + keyset_replays}"
    )


if __name__ == "__main__":
    main()
