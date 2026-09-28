import hashlib
import json

import pytest

from services import external_witness_roster_chain as chain


GENESIS_POLICY_SHA = (
    "a5c456d49e47f1be3f2a7b7ed017328"
    "844484ba05c4e6ef3212412c6361156c4"
)
GENESIS_STATE_SHA = (
    "19818486f5515d0d0e9f2ea86c1a2b1"
    "230abc2db4e0ac47b405566e06d6b6808"
)
GENESIS_CHECKPOINT_SHA = (
    "633fe8e596c47f04f60fb12d1ef61cb"
    "0e86e709d564e475162d9d5c030672611"
)
GENESIS_CHECKPOINT_TAG = (
    "183d97e29f0ce148a46592a411d7c4b8"
    "b9a939bdfc21cb20cee1bcae27152b66"
)
GENESIS_HEAD_SHA = (
    "7d45840c825f15861bf3368024b36e39"
    "422bd5f66a5f54ef6927bacd05f3cce5"
)
GENESIS_HEAD_TAG = (
    "d927fbc86f7e918447767c6048f1ba8a"
    "4ba5aa464ac578ba964583fc2192803b"
)


class Result:
    def __init__(self, data):
        self.data = data


class FakeDB:
    def __init__(self):
        self.records = []

    def rpc(self, name, params):
        db = self

        class Call:
            def execute(self):
                if name == (
                    "shine_ai_external_witness_roster_chain_snapshot_v1"
                ):
                    return Result({
                        "status": "empty" if not db.records else "ok",
                        "records": list(db.records),
                    })
                if name == (
                    "shine_ai_external_witness_roster_chain_append_v1"
                ):
                    existing = [
                        row
                        for row in db.records
                        if row["sequence"] == params["p_sequence"]
                    ]
                    record = {
                        "chainVersion": 1,
                        "chainType": chain.CHAIN_TYPE,
                        "authAlgorithm": "HMAC-SHA-256",
                        "authKeyId": params["p_auth_key_id"],
                        "sequence": params["p_sequence"],
                        "previousCheckpointSha256":
                            params["p_previous_checkpoint_sha256"],
                        "trustStateVersion": 1,
                        "generation": params["p_generation"],
                        "previousPolicySha256":
                            params["p_previous_policy_sha256"],
                        "policySha256": params["p_policy_sha256"],
                        "stateSha256": params["p_state_sha256"],
                        "checkpointSha256":
                            params["p_checkpoint_sha256"],
                        "authTag": params["p_auth_tag"],
                    }
                    if existing:
                        assert existing[0] == record
                        return Result({"status": "already_present"})
                    db.records.append(record)
                    db.records.sort(key=lambda row: row["sequence"])
                    return Result({"status": "appended"})
                raise AssertionError(name)

        return Call()


class FakeRedis:
    def __init__(self):
        self.rows = {}

    def hgetall(self, key):
        return dict(self.rows.get(key, {}))

    def eval(self, _script, _numkeys, key, *args):
        (
            sequence,
            checkpoint_sha,
            generation,
            policy_sha,
            state_sha,
            previous_checkpoint_sha,
            head_json,
        ) = args
        sequence = int(sequence)
        generation = int(generation)
        current = self.rows.get(key)

        if current is None:
            if sequence != 1 or previous_checkpoint_sha != "":
                return ["genesis-invalid"]
            self.rows[key] = {
                "sequence": str(sequence),
                "checkpoint_sha256": checkpoint_sha,
                "generation": str(generation),
                "policy_sha256": policy_sha,
                "state_sha256": state_sha,
                "head_json": head_json,
            }
            return ["created"]

        current_sequence = int(current["sequence"])
        if sequence < current_sequence:
            return ["rollback"]
        if sequence > current_sequence + 1:
            return ["sequence-skip"]
        if sequence == current_sequence:
            if (
                checkpoint_sha != current["checkpoint_sha256"]
                or generation != int(current["generation"])
                or policy_sha != current["policy_sha256"]
                or state_sha != current["state_sha256"]
            ):
                return ["fork"]
            current["head_json"] = head_json
            return ["refreshed"]

        if previous_checkpoint_sha != current["checkpoint_sha256"]:
            return ["predecessor-checkpoint-mismatch"]
        if generation != int(current["generation"]) + 1:
            return ["generation-mismatch"]

        self.rows[key] = {
            "sequence": str(sequence),
            "checkpoint_sha256": checkpoint_sha,
            "generation": str(generation),
            "policy_sha256": policy_sha,
            "state_sha256": state_sha,
            "head_json": head_json,
        }
        return ["advanced"]


@pytest.fixture(autouse=True)
def chain_keys(monkeypatch):
    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_CHAIN_KEYRING_JSON",
        json.dumps({
            "chain-a": "C" * 48,
            "chain-b": "D" * 48,
        }),
    )
    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_CHAIN_ACTIVE_KEY_ID",
        "chain-a",
    )


def genesis_state():
    return {
        "trustStateVersion": 1,
        "trustStateType": chain.TRUST_STATE_TYPE,
        "generation": 1,
        "minimumWitnesses": 2,
        "acceptedWitnessIds": [
            "foundation-project-l",
            "redis-project-l",
        ],
        "previousPolicySha256": None,
        "policySha256": GENESIS_POLICY_SHA,
    }


def next_state(previous):
    material = {
        "policyVersion": 1,
        "policyType": chain.TRUST_STATE_TYPE,
        "generation": previous["generation"] + 1,
        "minimumWitnesses": 2,
        "acceptedWitnessIds": [
            "foundation-project-l",
            "redis-project-l",
        ],
        "previousPolicySha256": previous["policySha256"],
    }
    policy_sha = hashlib.sha256(
        json.dumps(
            material,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "trustStateVersion": 1,
        "trustStateType": chain.TRUST_STATE_TYPE,
        "generation": material["generation"],
        "minimumWitnesses": material["minimumWitnesses"],
        "acceptedWitnessIds": material["acceptedWitnessIds"],
        "previousPolicySha256": material["previousPolicySha256"],
        "policySha256": policy_sha,
    }


def test_layer161_genesis_vectors_match_contract():
    state = genesis_state()
    checkpoint = chain.create_checkpoint(
        state,
        auth_key_id="chain-a",
    )
    head = chain.create_head(
        checkpoint,
        auth_key_id="chain-a",
    )

    assert chain.digest_state(state) == GENESIS_STATE_SHA
    assert checkpoint["checkpointSha256"] == GENESIS_CHECKPOINT_SHA
    assert checkpoint["authTag"] == GENESIS_CHECKPOINT_TAG
    assert head["headSha256"] == GENESIS_HEAD_SHA
    assert head["authTag"] == GENESIS_HEAD_TAG
    assert chain.verify_checkpoint(checkpoint) == checkpoint
    assert chain.verify_head(head) == head


def test_auth_key_rotation_does_not_change_stable_chain_identity():
    checkpoint_a = chain.create_checkpoint(
        genesis_state(),
        auth_key_id="chain-a",
    )
    checkpoint_b = chain.create_checkpoint(
        genesis_state(),
        auth_key_id="chain-b",
    )
    head_a = chain.create_head(
        checkpoint_a,
        auth_key_id="chain-a",
    )
    head_b = chain.create_head(
        checkpoint_b,
        auth_key_id="chain-b",
    )

    assert (
        checkpoint_a["checkpointSha256"]
        == checkpoint_b["checkpointSha256"]
    )
    assert checkpoint_a["authTag"] != checkpoint_b["authTag"]
    assert head_a["headSha256"] == head_b["headSha256"]
    assert head_a["authTag"] != head_b["authTag"]


def test_ensure_chain_bootstraps_and_is_idempotent():
    db = FakeDB()
    redis = FakeRedis()

    first = chain.ensure_roster_chain(
        db,
        genesis_state(),
        redis_client=redis,
    )
    second = chain.ensure_roster_chain(
        db,
        genesis_state(),
        redis_client=redis,
    )

    assert first["status"] == "verified"
    assert first["sequence"] == 1
    assert first["checkpoint_sha256"] == GENESIS_CHECKPOINT_SHA
    assert first["head_sha256"] == GENESIS_HEAD_SHA
    assert first["head_independent_retention"] == "railway-redis-volume"
    assert second["head_mode"] == "refreshed"
    assert len(db.records) == 1


def test_chain_advances_exactly_one_generation():
    db = FakeDB()
    redis = FakeRedis()
    state1 = genesis_state()
    state2 = next_state(state1)

    chain.ensure_roster_chain(db, state1, redis_client=redis)
    receipt = chain.ensure_roster_chain(
        db,
        state2,
        redis_client=redis,
    )

    assert receipt["sequence"] == 2
    assert receipt["generation"] == 2
    assert receipt["previous_checkpoint_sha256"] == GENESIS_CHECKPOINT_SHA
    assert receipt["head_mode"] == "advanced"
    assert receipt["history_records_verified"] == 2


def test_chain_rejects_truncated_or_skipped_history():
    db = FakeDB()
    redis = FakeRedis()
    state1 = genesis_state()
    state2 = next_state(state1)
    state3 = next_state(state2)

    cp1 = chain.create_checkpoint(state1)
    cp2 = chain.create_checkpoint(
        state2,
        previous_checkpoint=cp1,
    )
    cp3 = chain.create_checkpoint(
        state3,
        previous_checkpoint=cp2,
    )

    with pytest.raises(
        chain.ExternalWitnessRosterChainError,
        match="external-witness-roster-chain-continuity-invalid",
    ):
        chain.verify_chain([cp1, cp3])

    with pytest.raises(
        chain.ExternalWitnessRosterChainError,
        match="external-witness-roster-chain-history-missing",
    ):
        chain.ensure_roster_chain(db, state2, redis_client=redis)


def test_chain_rejects_forged_predecessor():
    cp1 = chain.create_checkpoint(genesis_state())
    state2 = next_state(genesis_state())
    cp2 = chain.create_checkpoint(
        state2,
        previous_checkpoint=cp1,
    )
    forged = dict(cp2)
    forged["previousCheckpointSha256"] = "f" * 64

    with pytest.raises(
        chain.ExternalWitnessRosterChainError,
        match="external-witness-roster-chain-checkpoint-digest-mismatch",
    ):
        chain.verify_checkpoint(forged)


def test_newer_redis_head_rejects_historical_chain():
    db = FakeDB()
    redis = FakeRedis()
    state1 = genesis_state()
    state2 = next_state(state1)

    chain.ensure_roster_chain(db, state1, redis_client=redis)
    chain.ensure_roster_chain(db, state2, redis_client=redis)

    historical_db = FakeDB()
    historical_db.records = [db.records[0]]

    with pytest.raises(
        chain.ExternalWitnessRosterChainError,
        match="external-witness-roster-head-cas-rollback",
    ):
        chain.ensure_roster_chain(
            historical_db,
            state1,
            redis_client=redis,
        )


def test_head_pin_rejects_older_valid_head():
    cp = chain.create_checkpoint(genesis_state())
    head = chain.create_head(cp)

    with pytest.raises(
        chain.ExternalWitnessRosterChainError,
        match="external-witness-roster-head-pin-mismatch",
    ):
        chain.verify_head(
            head,
            expected_head_sha256="f" * 64,
        )
