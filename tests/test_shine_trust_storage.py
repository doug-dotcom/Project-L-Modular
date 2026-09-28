import json

import pytest

from services import shine_trust_storage as storage


SINGLE_KEYSET_SHA256 = (
    "00d100d5873dd2fecc3049dc501b2f2f"
    "5dfc268710858b9cf68b0f5858666f4a"
)
OVERLAP_KEYSET_SHA256 = (
    "5d9919a8cf9453a330016410e2903d75"
    "56a170d7ce95450dc4a90cab366cd9ca"
)
PUBLIC_A_B64 = "A6EHv/POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg="
PUBLIC_A_SHA = (
    "56475aa75463474c0285df5dbf2bcab7"
    "3da651358839e9b77481b2eab107708c"
)
PUBLIC_B_B64 = "Kay64UG8yvCyLhqU000LxzYeUm0L/hLIl5S8kyKWbdc="
PUBLIC_B_SHA = (
    "24f6ed6acbfe1009c030d7ca567c33ca"
    "4830911498236b5561a6c82abec5de28"
)
EXPECTED_STATE_SHA = (
    "f7293d3106e352eb82db8e410626b66c"
    "706db83f423e938528d7cdae693f2dee"
)
EXPECTED_ENVELOPE_TAG = (
    "8ca905c679da046f7d2accad0e6d1d00"
    "aea41d56a6f516892de765dfc7c88091"
)
EXPECTED_CHECKPOINT_TAG = (
    "fb11799cc06cc2da11c8b8836dd673a9"
    "3479ae213ac50c47b2ebf148c71f7761"
)


class FakeRedis:
    def __init__(self):
        self.rows = {}

    def hgetall(self, key):
        return dict(self.rows.get(key, {}))

    def eval(self, _script, _numkeys, key, *args):
        if len(args) == 7:
            (
                expected_generation,
                expected_state_sha,
                expected_keyset_sha,
                next_generation,
                next_state_sha,
                next_keyset_sha,
                checkpoint_json,
            ) = args
            expected_generation = int(expected_generation)
            next_generation = int(next_generation)
            current = self.rows.get(key)

            if current is None:
                if expected_generation != 0:
                    return ["missing"]
                self.rows[key] = {
                    "generation": str(next_generation),
                    "state_sha256": next_state_sha,
                    "keyset_sha256": next_keyset_sha,
                    "checkpoint_json": checkpoint_json,
                }
                return ["created"]

            current_generation = int(current["generation"])
            if current_generation != expected_generation:
                return ["precondition-generation", str(current_generation)]
            if current["state_sha256"] != expected_state_sha:
                return ["precondition-state", current["state_sha256"]]
            if current["keyset_sha256"] != expected_keyset_sha:
                return ["precondition-keyset", current["keyset_sha256"]]
            if next_generation < current_generation:
                return ["rollback"]
            if next_generation > current_generation + 1:
                return ["generation-skip"]
            if (
                next_generation == current_generation
                and next_keyset_sha != current["keyset_sha256"]
            ):
                return ["equivocation"]

            self.rows[key] = {
                "generation": str(next_generation),
                "state_sha256": next_state_sha,
                "keyset_sha256": next_keyset_sha,
                "checkpoint_json": checkpoint_json,
            }
            return [
                "refreshed"
                if next_generation == current_generation
                else "advanced"
            ]

        if len(args) == 5:
            (
                expected_sequence,
                expected_head_sha,
                next_sequence,
                next_head_sha,
                head_json,
            ) = args
            expected_sequence = int(expected_sequence)
            next_sequence = int(next_sequence)
            current = self.rows.get(key)
            if current is None:
                if expected_sequence != 0 or next_sequence != 1:
                    return ["missing"]
                self.rows[key] = {
                    "sequence": str(next_sequence),
                    "head_sha256": next_head_sha,
                    "head_json": head_json,
                }
                return ["created"]
            if int(current["sequence"]) != expected_sequence:
                return [
                    "precondition-sequence",
                    current["sequence"],
                ]
            if current["head_sha256"] != expected_head_sha:
                return [
                    "precondition-head",
                    current["head_sha256"],
                ]
            if next_sequence != expected_sequence + 1:
                return ["sequence-invalid"]
            self.rows[key] = {
                "sequence": str(next_sequence),
                "head_sha256": next_head_sha,
                "head_json": head_json,
            }
            return ["advanced"]

        raise AssertionError(args)


@pytest.fixture(autouse=True)
def storage_keys(monkeypatch):
    monkeypatch.setenv(
        "SHINE_AI_TRUST_STATE_STORAGE_KEYRING_JSON",
        json.dumps(
            {
                "storage-a": "S" * 48,
                "storage-b": "T" * 48,
            }
        ),
    )
    monkeypatch.setenv(
        "SHINE_AI_TRUST_STATE_STORAGE_ACTIVE_KEY_ID",
        "storage-a",
    )


def single_state():
    return {
        "version": 1,
        "generation": 1,
        "active_key_id": "trace-v1",
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": PUBLIC_A_B64,
                "public_key_sha256": PUBLIC_A_SHA,
            },
        },
        "keyset_sha256": SINGLE_KEYSET_SHA256,
    }


def overlap_state(active="trace-v1", generation=2):
    return {
        "version": 1,
        "generation": generation,
        "active_key_id": active,
        "verification_keys": {
            "trace-v1": {
                "public_key_b64": PUBLIC_A_B64,
                "public_key_sha256": PUBLIC_A_SHA,
            },
            "trace-v2": {
                "public_key_b64": PUBLIC_B_B64,
                "public_key_sha256": PUBLIC_B_SHA,
            },
        },
        "keyset_sha256": OVERLAP_KEYSET_SHA256,
    }


def test_layer143_canonical_state_and_envelope_vector():
    state = single_state()

    assert storage.digest_trust_state(state) == EXPECTED_STATE_SHA
    envelope = storage.create_authenticated_envelope(
        state,
        auth_key_id="storage-a",
    )

    assert envelope["stateSha256"] == EXPECTED_STATE_SHA
    assert envelope["authTag"] == EXPECTED_ENVELOPE_TAG
    assert storage.verify_authenticated_envelope(envelope) == state


def test_layer143_checkpoint_vector():
    checkpoint = storage.create_rollback_checkpoint(
        single_state(),
        auth_key_id="storage-a",
    )

    assert checkpoint["stateSha256"] == EXPECTED_STATE_SHA
    assert checkpoint["authTag"] == EXPECTED_CHECKPOINT_TAG
    assert storage.verify_rollback_checkpoint(checkpoint) == checkpoint


def test_envelope_and_checkpoint_fail_on_tampering():
    envelope = storage.create_authenticated_envelope(single_state())
    envelope["stateSha256"] = "0" * 64
    with pytest.raises(
        storage.TrustStorageError,
        match="trust-state-envelope-digest-mismatch",
    ):
        storage.verify_authenticated_envelope(envelope)

    checkpoint = storage.create_rollback_checkpoint(single_state())
    checkpoint["authTag"] = "0" * 64
    with pytest.raises(
        storage.TrustStorageError,
        match="trust-checkpoint-auth-failed",
    ):
        storage.verify_rollback_checkpoint(checkpoint)


def test_genesis_checkpoint_is_idempotent_and_independent():
    redis = FakeRedis()
    state = single_state()

    first = storage.prepare_rollback_checkpoint(
        state,
        allow_genesis=True,
        redis_client=redis,
    )
    second = storage.prepare_rollback_checkpoint(
        state,
        allow_genesis=True,
        redis_client=redis,
    )

    assert first["mode"] == "created"
    assert second["mode"] == "existing-checkpoint"
    verified = storage.verify_state_against_checkpoint(
        state,
        redis_client=redis,
    )
    assert verified["status"] == "verified"
    assert verified["independent_retention"] == "railway-redis-volume"


def test_same_generation_active_key_observation_moves_checkpoint_forward():
    redis = FakeRedis()
    previous = overlap_state("trace-v1", generation=2)
    current = overlap_state("trace-v2", generation=2)

    # Seed generation 2 through the exact persisted Redis representation;
    # no-predecessor creation is intentionally generation-1 only.
    previous_cp = storage.create_rollback_checkpoint(previous)
    redis.rows[storage.REDIS_CHECKPOINT_KEY] = {
        "generation": "2",
        "state_sha256": previous_cp["stateSha256"],
        "keyset_sha256": previous_cp["keyset_sha256"],
        "checkpoint_json": json.dumps(
            previous_cp,
            separators=(",", ":"),
        ),
    }

    result = storage.prepare_rollback_checkpoint(
        current,
        previous_state=previous,
        redis_client=redis,
    )

    assert result["mode"] == "refreshed"
    assert storage.verify_state_against_checkpoint(
        current,
        redis_client=redis,
    )["status"] == "verified"
    with pytest.raises(
        storage.TrustStorageError,
        match="trust-checkpoint-active-observation-rollback",
    ):
        storage.verify_state_against_checkpoint(
            previous,
            redis_client=redis,
        )


def test_checkpoint_advances_exactly_one_generation():
    redis = FakeRedis()
    previous = single_state()
    current = overlap_state("trace-v2", generation=2)

    storage.prepare_rollback_checkpoint(
        previous,
        allow_genesis=True,
        redis_client=redis,
    )
    result = storage.prepare_rollback_checkpoint(
        current,
        previous_state=previous,
        redis_client=redis,
    )

    assert result["mode"] == "advanced"
    assert storage.verify_state_against_checkpoint(
        current,
        redis_client=redis,
    )["generation"] == 2


def test_checkpoint_rejects_rollback_and_unrelated_state():
    redis = FakeRedis()
    previous = single_state()
    current = overlap_state("trace-v2", generation=2)
    storage.prepare_rollback_checkpoint(
        previous,
        allow_genesis=True,
        redis_client=redis,
    )
    storage.prepare_rollback_checkpoint(
        current,
        previous_state=previous,
        redis_client=redis,
    )

    with pytest.raises(
        storage.TrustStorageError,
        match="trust-checkpoint-rollback-detected",
    ):
        storage.verify_state_against_checkpoint(
            previous,
            redis_client=redis,
        )

    fork = overlap_state("trace-v1", generation=2)
    with pytest.raises(
        storage.TrustStorageError,
        match="trust-checkpoint-active-observation-rollback",
    ):
        storage.verify_state_against_checkpoint(
            fork,
            redis_client=redis,
        )


def test_retired_storage_key_stops_old_checkpoint_verification(monkeypatch):
    checkpoint = storage.create_rollback_checkpoint(
        single_state(),
        auth_key_id="storage-a",
    )
    monkeypatch.setenv(
        "SHINE_AI_TRUST_STATE_STORAGE_KEYRING_JSON",
        json.dumps({"storage-b": "T" * 48}),
    )
    monkeypatch.setenv(
        "SHINE_AI_TRUST_STATE_STORAGE_ACTIVE_KEY_ID",
        "storage-b",
    )

    with pytest.raises(
        storage.TrustStorageError,
        match="trust-storage-auth-key-retired",
    ):
        storage.verify_rollback_checkpoint(checkpoint)



def test_monotonic_head_bootstraps_and_is_idempotent():
    redis = FakeRedis()
    state = single_state()
    storage.prepare_rollback_checkpoint(
        state,
        allow_genesis=True,
        redis_client=redis,
    )

    first = storage.prepare_monotonic_head(
        state,
        redis_client=redis,
    )
    second = storage.prepare_monotonic_head(
        state,
        redis_client=redis,
    )

    assert first["mode"] == "created"
    assert first["head"]["sequence"] == 1
    assert second["mode"] == "existing-head"
    assert second["head"]["headSha256"] == first["head"]["headSha256"]
    assert storage.verify_monotonic_head(
        first["head"]
    )["headSha256"] == first["head"]["headSha256"]


def test_monotonic_head_advances_on_active_key_observation():
    redis = FakeRedis()
    previous = overlap_state("trace-v1", generation=2)
    current = overlap_state("trace-v2", generation=2)

    previous_cp = storage.create_rollback_checkpoint(previous)
    redis.rows[storage.REDIS_CHECKPOINT_KEY] = {
        "generation": "2",
        "state_sha256": previous_cp["stateSha256"],
        "keyset_sha256": previous_cp["keyset_sha256"],
        "checkpoint_json": json.dumps(
            previous_cp,
            separators=(",", ":"),
        ),
    }
    first = storage.prepare_monotonic_head(
        previous,
        redis_client=redis,
    )

    storage.prepare_rollback_checkpoint(
        current,
        previous_state=previous,
        redis_client=redis,
    )
    second = storage.prepare_monotonic_head(
        current,
        redis_client=redis,
    )

    assert first["head"]["sequence"] == 1
    assert second["mode"] == "advanced"
    assert second["head"]["sequence"] == 2
    assert second["head"]["generation"] == 2
    assert (
        second["head"]["keyset_sha256"]
        == first["head"]["keyset_sha256"]
    )
    assert (
        second["head"]["stateSha256"]
        != first["head"]["stateSha256"]
    )


def test_monotonic_head_advances_generation_and_rejects_rollback():
    redis = FakeRedis()
    previous = single_state()
    current = overlap_state("trace-v2", generation=2)

    storage.prepare_rollback_checkpoint(
        previous,
        allow_genesis=True,
        redis_client=redis,
    )
    first = storage.prepare_monotonic_head(
        previous,
        redis_client=redis,
    )
    storage.prepare_rollback_checkpoint(
        current,
        previous_state=previous,
        redis_client=redis,
    )
    second = storage.prepare_monotonic_head(
        current,
        redis_client=redis,
    )

    assert first["head"]["sequence"] == 1
    assert second["head"]["sequence"] == 2
    assert second["head"]["generation"] == 2
    assert (
        second["head"]["keyset_sha256"]
        != first["head"]["keyset_sha256"]
    )

    with pytest.raises(
        storage.TrustStorageError,
        match="trust-head-checkpoint-state-mismatch",
    ):
        storage.prepare_monotonic_head(
            previous,
            redis_client=redis,
        )


def test_monotonic_head_authentication_rejects_tampering():
    redis = FakeRedis()
    state = single_state()
    storage.prepare_rollback_checkpoint(
        state,
        allow_genesis=True,
        redis_client=redis,
    )
    result = storage.prepare_monotonic_head(
        state,
        redis_client=redis,
    )
    tampered = dict(result["head"])
    tampered["headSha256"] = "0" * 64

    with pytest.raises(
        storage.TrustStorageError,
        match="trust-head-digest-mismatch",
    ):
        storage.verify_monotonic_head(tampered)
