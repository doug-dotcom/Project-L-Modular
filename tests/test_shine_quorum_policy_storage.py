import json

import pytest

from services import shine_quorum_policy_storage as storage


POLICY_SHA = (
    "26b6d1a3b4183cfa596f8c9c06c18e73"
    "aa0eda6a80a6362649130e9357bf220e"
)
EXPECTED_STATE_SHA = (
    "5a444bfc1b3816def3ad06530303f497"
    "c3579ca1b3c1afb19da6e2bc167f633b"
)
EXPECTED_ENVELOPE_TAG = (
    "2f55cca528a82d5816c3cdec8a860fed"
    "325deabe5abd5974b54a4f05b3065a60"
)
EXPECTED_CHECKPOINT_TAG = (
    "862e097f75b2ebd153f689f01ecba634"
    "d8b0077c6475c6180a050272922009b8"
)


class FakeRedis:
    def __init__(self):
        self.rows = {}

    def hgetall(self, key):
        return dict(self.rows.get(key, {}))

    def eval(self, _script, _numkeys, key, *args):
        generation, policy_sha, state_sha, checkpoint_json = args
        generation = int(generation)
        current = self.rows.get(key)
        if current is None:
            if generation != 1:
                return ["bootstrap-generation-invalid"]
            self.rows[key] = {
                "generation": str(generation),
                "policy_sha256": policy_sha,
                "state_sha256": state_sha,
                "checkpoint_json": checkpoint_json,
            }
            return ["created"]

        current_generation = int(current["generation"])
        if generation < current_generation:
            return ["rollback"]
        if generation > current_generation:
            return ["generation-transition-unimplemented"]
        if current["policy_sha256"] != policy_sha:
            return ["equivocation"]
        if current["state_sha256"] != state_sha:
            return ["state-mismatch"]
        self.rows[key]["checkpoint_json"] = checkpoint_json
        return ["refreshed"]


@pytest.fixture(autouse=True)
def policy_storage_env(monkeypatch):
    monkeypatch.setenv(
        "SHINE_TRACE_WITNESS_QUORUM_POLICY_STORAGE_KEYRING_JSON",
        json.dumps({
            "policy-a": "S" * 48,
            "policy-b": "T" * 48,
        }),
    )
    monkeypatch.setenv(
        "SHINE_TRACE_WITNESS_QUORUM_POLICY_STORAGE_ACTIVE_KEY_ID",
        "policy-a",
    )


def policy_state():
    return {
        "trustStateVersion": 1,
        "trustStateType":
            "decision_trace_trust_state_witness_quorum_policy",
        "generation": 1,
        "minimumWitnesses": 2,
        "acceptedWitnessIds": [
            "foundation-project-l",
            "redis-project-l",
        ],
        "previousPolicySha256": None,
        "policySha256": POLICY_SHA,
    }


def test_layer152_policy_storage_golden_vector():
    state = policy_state()

    assert storage.digest_policy_state(state) == EXPECTED_STATE_SHA

    envelope = storage.create_envelope(
        state,
        auth_key_id="policy-a",
    )
    checkpoint = storage.create_checkpoint(
        state,
        auth_key_id="policy-a",
    )

    assert envelope["stateSha256"] == EXPECTED_STATE_SHA
    assert envelope["authTag"] == EXPECTED_ENVELOPE_TAG
    assert checkpoint["stateSha256"] == EXPECTED_STATE_SHA
    assert checkpoint["authTag"] == EXPECTED_CHECKPOINT_TAG
    assert storage.verify_pair(envelope, checkpoint) == state


def test_policy_storage_rotation_preserves_exact_policy_state():
    state = policy_state()
    source_envelope = storage.create_envelope(
        state,
        auth_key_id="policy-a",
    )
    source_checkpoint = storage.create_checkpoint(
        state,
        auth_key_id="policy-a",
    )

    rotated = storage.rotate_pair(
        source_envelope,
        source_checkpoint,
        "policy-b",
    )

    assert rotated["receipt"]["sourceEnvelopeAuthKeyId"] == "policy-a"
    assert rotated["receipt"]["sourceCheckpointAuthKeyId"] == "policy-a"
    assert rotated["receipt"]["targetAuthKeyId"] == "policy-b"
    assert rotated["receipt"]["generation"] == 1
    assert rotated["receipt"]["policySha256"] == POLICY_SHA
    assert rotated["receipt"]["stateSha256"] == EXPECTED_STATE_SHA
    assert storage.verify_pair(
        rotated["envelope"],
        rotated["checkpoint"],
    ) == state
    assert rotated["envelope"]["state"] == source_envelope["state"]
    assert (
        rotated["envelope"]["stateSha256"]
        == source_envelope["stateSha256"]
    )


def test_partial_overlap_rotation_recovers_when_checkpoint_already_target():
    state = policy_state()
    source_envelope = storage.create_envelope(
        state,
        auth_key_id="policy-a",
    )
    target_checkpoint = storage.create_checkpoint(
        state,
        auth_key_id="policy-b",
    )

    rotated = storage.rotate_pair(
        source_envelope,
        target_checkpoint,
        "policy-b",
    )

    assert rotated["receipt"]["sourceEnvelopeAuthKeyId"] == "policy-a"
    assert rotated["receipt"]["sourceCheckpointAuthKeyId"] == "policy-b"
    assert storage.verify_pair(
        rotated["envelope"],
        rotated["checkpoint"],
    ) == state


def test_rotation_noop_and_missing_target_fail_closed():
    state = policy_state()
    envelope = storage.create_envelope(
        state,
        auth_key_id="policy-a",
    )
    checkpoint = storage.create_checkpoint(
        state,
        auth_key_id="policy-a",
    )

    with pytest.raises(
        storage.QuorumPolicyStorageError,
        match="rotation-noop",
    ):
        storage.rotate_pair(envelope, checkpoint, "policy-a")

    with pytest.raises(
        storage.QuorumPolicyStorageError,
        match="target-key-unavailable",
    ):
        storage.rotate_pair(envelope, checkpoint, "policy-missing")


def test_retired_source_key_stops_old_storage_from_verifying(monkeypatch):
    state = policy_state()
    envelope = storage.create_envelope(
        state,
        auth_key_id="policy-a",
    )
    checkpoint = storage.create_checkpoint(
        state,
        auth_key_id="policy-a",
    )

    monkeypatch.setenv(
        "SHINE_TRACE_WITNESS_QUORUM_POLICY_STORAGE_KEYRING_JSON",
        json.dumps({"policy-b": "T" * 48}),
    )
    monkeypatch.setenv(
        "SHINE_TRACE_WITNESS_QUORUM_POLICY_STORAGE_ACTIVE_KEY_ID",
        "policy-b",
    )

    with pytest.raises(
        storage.QuorumPolicyStorageError,
        match="key-retired",
    ):
        storage.verify_pair(envelope, checkpoint)


def test_policy_checkpoint_is_idempotent_and_contains_no_policy_secret():
    redis = FakeRedis()
    state = policy_state()

    first = storage.persist_checkpoint(
        state,
        auth_key_id="policy-a",
        redis_client=redis,
    )
    second = storage.persist_checkpoint(
        state,
        auth_key_id="policy-a",
        redis_client=redis,
    )

    assert first["mode"] == "created"
    assert second["mode"] == "refreshed"
    stored = storage.read_checkpoint(redis_client=redis)
    assert stored["generation"] == 1
    assert stored["policySha256"] == POLICY_SHA
    assert "acceptedWitnessIds" not in redis.rows[
        storage.REDIS_POLICY_CHECKPOINT_KEY
    ]
