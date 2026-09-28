import json

import pytest

from services import external_witness_roster as roster


POLICY_SHA = (
    "a5c456d49e47f1be3f2a7b7ed017328"
    "844484ba05c4e6ef3212412c6361156c4"
)
STATE_SHA = (
    "19818486f5515d0d0e9f2ea86c1a2b12"
    "30abc2db4e0ac47b405566e06d6b6808"
)
ENVELOPE_TAG = (
    "85be7b7299af4dbcd906803443f753d3"
    "244103d3b3d5150422ab3809f028b97e"
)
CHECKPOINT_TAG = (
    "83fe07168ac243ae0657293d98e13a27"
    "3d4ddaf0bd0b051f2577dcd2b7b574b3"
)


def policy():
    return {
        "policyVersion": 1,
        "policyType": roster.ROSTER_POLICY_TYPE,
        "generation": 1,
        "minimumWitnesses": 2,
        "acceptedWitnessIds": [
            "foundation-project-l",
            "redis-project-l",
        ],
        "previousPolicySha256": None,
        "policySha256": POLICY_SHA,
    }


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeDB:
    def __init__(self):
        self.state = None
        self.rpc_calls = []

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        db = self

        class Call:
            def execute(self):
                if name == "shine_ai_external_witness_roster_snapshot_v1":
                    if db.state is None:
                        return FakeResult({"status": "unbootstrapped"})
                    return FakeResult({
                        "status": "trusted",
                        "trust_state": dict(db.state["trust_state"]),
                        "state_sha256": db.state["state_sha256"],
                        "storage_auth_key_id":
                            db.state["storage_auth_key_id"],
                        "storage_auth_tag": db.state["storage_auth_tag"],
                    })
                if name == "shine_ai_external_witness_roster_bootstrap_v1":
                    state = roster.policy_to_trust_state(policy())
                    db.state = {
                        "trust_state": state,
                        "state_sha256": params["p_state_sha256"],
                        "storage_auth_key_id":
                            params["p_storage_auth_key_id"],
                        "storage_auth_tag": params["p_storage_auth_tag"],
                    }
                    return FakeResult({
                        "status": "trusted",
                        "trust_state": dict(state),
                    })
                if name == "shine_ai_external_witness_roster_rotate_storage_v1":
                    assert db.state is not None
                    assert (
                        db.state["trust_state"]["generation"]
                        == params["p_expected_generation"]
                    )
                    assert (
                        db.state["trust_state"]["policySha256"]
                        == params["p_expected_policy_sha256"]
                    )
                    assert (
                        db.state["state_sha256"]
                        == params["p_expected_state_sha256"]
                    )
                    if (
                        db.state["storage_auth_key_id"]
                        == params["p_target_storage_auth_key_id"]
                    ):
                        if (
                            db.state["storage_auth_tag"]
                            != params["p_target_storage_auth_tag"]
                        ):
                            raise AssertionError("target tag mismatch")
                        return FakeResult({
                            "status": "already_rotated",
                            "generation":
                                params["p_expected_generation"],
                            "policy_sha256":
                                params["p_expected_policy_sha256"],
                            "state_sha256":
                                params["p_expected_state_sha256"],
                            "storage_auth_key_id":
                                params["p_target_storage_auth_key_id"],
                        })
                    assert (
                        db.state["storage_auth_key_id"]
                        == params["p_expected_storage_auth_key_id"]
                    )
                    db.state["storage_auth_key_id"] = (
                        params["p_target_storage_auth_key_id"]
                    )
                    db.state["storage_auth_tag"] = (
                        params["p_target_storage_auth_tag"]
                    )
                    return FakeResult({
                        "status": "rotated",
                        "generation": params["p_expected_generation"],
                        "policy_sha256": params["p_expected_policy_sha256"],
                        "state_sha256": params["p_expected_state_sha256"],
                        "storage_auth_key_id":
                            params["p_target_storage_auth_key_id"],
                    })
                raise AssertionError(name)

        return Call()


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
        if generation > current_generation + 1:
            return ["generation-skip"]
        if generation == current_generation:
            if current["policy_sha256"] != policy_sha:
                return ["equivocation"]
            if current["state_sha256"] != state_sha:
                return ["state-mismatch"]
            current["checkpoint_json"] = checkpoint_json
            return ["refreshed"]
        return ["transition-unimplemented"]


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_POLICY_JSON",
        json.dumps(policy()),
    )
    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_GENESIS_SHA256",
        POLICY_SHA,
    )
    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_KEYRING_JSON",
        json.dumps({
            "roster-a": "S" * 48,
            "roster-b": "T" * 48,
        }),
    )
    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_ACTIVE_KEY_ID",
        "roster-a",
    )


def test_genesis_policy_matches_layer157_vector():
    value = roster.load_genesis_policy()

    assert value == policy()
    assert value["policySha256"] == POLICY_SHA


def test_layer159_storage_vectors_match_contract():
    state = roster.policy_to_trust_state(policy())

    assert roster.digest_trust_state(state) == STATE_SHA
    envelope = roster.create_envelope(
        state,
        auth_key_id="roster-a",
    )
    checkpoint = roster.create_checkpoint(
        state,
        auth_key_id="roster-a",
    )

    assert envelope["stateSha256"] == STATE_SHA
    assert envelope["authTag"] == ENVELOPE_TAG
    assert checkpoint["stateSha256"] == STATE_SHA
    assert checkpoint["authTag"] == CHECKPOINT_TAG
    assert roster.verify_envelope(envelope) == state
    assert roster.verify_checkpoint(checkpoint) == checkpoint
    assert roster.verify_pair(envelope, checkpoint) == state


def test_authenticated_roster_bootstraps_and_survives_restart():
    db = FakeDB()
    redis = FakeRedis()

    first = roster.load_persisted_external_witness_roster(
        db,
        redis_client=redis,
    )
    second = roster.load_persisted_external_witness_roster(
        db,
        redis_client=redis,
    )

    assert first["generation"] == 1
    assert first["minimumWitnesses"] == 2
    assert first["acceptedWitnessIds"] == [
        "foundation-project-l",
        "redis-project-l",
    ]
    assert first["roster_trust_persisted"] is True
    assert first["roster_storage_authenticated"] is True
    assert (
        first["roster_storage_checkpoint_retention"]
        == "railway-redis-volume"
    )
    assert second == first


def test_tampered_supabase_hmac_fails_closed():
    db = FakeDB()
    redis = FakeRedis()
    roster.load_persisted_external_witness_roster(
        db,
        redis_client=redis,
    )
    db.state["storage_auth_tag"] = "0" * 64

    with pytest.raises(
        roster.ExternalWitnessRosterError,
        match="external-witness-roster-storage-envelope-auth-failed",
    ):
        roster.load_persisted_external_witness_roster(
            db,
            redis_client=redis,
        )


def test_missing_independent_checkpoint_fails_closed():
    db = FakeDB()
    redis = FakeRedis()
    roster.load_persisted_external_witness_roster(
        db,
        redis_client=redis,
    )
    redis.rows.clear()

    with pytest.raises(
        roster.ExternalWitnessRosterError,
        match="external-witness-roster-storage-checkpoint-missing",
    ):
        roster.load_persisted_external_witness_roster(
            db,
            redis_client=redis,
        )


def test_same_generation_roster_fork_is_rejected(monkeypatch):
    db = FakeDB()
    redis = FakeRedis()
    roster.load_persisted_external_witness_roster(
        db,
        redis_client=redis,
    )
    fork = policy()
    fork["acceptedWitnessIds"] = [
        "foundation-project-l",
        "other-witness",
    ]
    material = {
        key: fork[key]
        for key in (
            "policyVersion",
            "policyType",
            "generation",
            "minimumWitnesses",
            "acceptedWitnessIds",
            "previousPolicySha256",
        )
    }
    fork["policySha256"] = roster._sha256_text(
        roster._canonical_json(material)
    )
    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_POLICY_JSON",
        json.dumps(fork),
    )

    with pytest.raises(
        roster.ExternalWitnessRosterError,
        match="external-witness-roster-equivocation-detected",
    ):
        roster.load_persisted_external_witness_roster(
            db,
            redis_client=redis,
        )


def test_future_generation_requires_separate_transition_certification(
    monkeypatch,
):
    db = FakeDB()
    redis = FakeRedis()
    roster.load_persisted_external_witness_roster(
        db,
        redis_client=redis,
    )
    candidate = policy()
    candidate["generation"] = 2
    candidate["previousPolicySha256"] = POLICY_SHA
    candidate["acceptedWitnessIds"] = [
        "foundation-project-l",
        "new-independent-witness",
        "redis-project-l",
    ]
    candidate["minimumWitnesses"] = 2
    material = {
        key: candidate[key]
        for key in (
            "policyVersion",
            "policyType",
            "generation",
            "minimumWitnesses",
            "acceptedWitnessIds",
            "previousPolicySha256",
        )
    }
    candidate["policySha256"] = roster._sha256_text(
        roster._canonical_json(material)
    )
    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_POLICY_JSON",
        json.dumps(candidate),
    )

    with pytest.raises(
        roster.ExternalWitnessRosterError,
        match="external-witness-roster-transition-not-certified",
    ):
        roster.load_persisted_external_witness_roster(
            db,
            redis_client=redis,
        )


def test_storage_key_retirement_fails_old_envelope(monkeypatch):
    envelope = roster.create_envelope(
        roster.policy_to_trust_state(policy()),
        auth_key_id="roster-a",
    )
    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_KEYRING_JSON",
        json.dumps({"roster-b": "T" * 48}),
    )
    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_ACTIVE_KEY_ID",
        "roster-b",
    )

    with pytest.raises(
        roster.ExternalWitnessRosterError,
        match="external-witness-roster-storage-key-retired",
    ):
        roster.verify_envelope(envelope)



def enable_rotation_target(monkeypatch):
    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_ROTATION_TARGET_KEY_ID",
        "roster-b-2026-09",
    )
    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_ROTATION_TARGET_SECRET",
        "U" * 48,
    )


def test_storage_key_rotation_preserves_exact_roster_state(monkeypatch):
    db = FakeDB()
    redis = FakeRedis()
    before = roster.load_persisted_external_witness_roster(
        db,
        redis_client=redis,
    )
    original_state = dict(db.state["trust_state"])
    original_state_sha = db.state["state_sha256"]
    original_policy_sha = original_state["policySha256"]

    enable_rotation_target(monkeypatch)
    receipt = roster.rotate_storage_authentication(
        db,
        redis_client=redis,
    )

    assert receipt["status"] == "verified"
    assert receipt["mode"] == "rotated"
    assert receipt["state_preserved"] is True
    assert receipt["generation"] == before["generation"]
    assert receipt["policy_sha256"] == original_policy_sha
    assert receipt["state_sha256"] == original_state_sha
    assert receipt["target_key_id"] == "roster-b-2026-09"
    assert db.state["trust_state"] == original_state
    assert db.state["state_sha256"] == original_state_sha
    assert db.state["storage_auth_key_id"] == "roster-b-2026-09"

    checkpoint = roster.read_checkpoint(redis_client=redis)
    assert checkpoint["authKeyId"] == "roster-b-2026-09"
    assert checkpoint["stateSha256"] == original_state_sha


def test_partial_redis_first_rotation_recovers_idempotently(monkeypatch):
    db = FakeDB()
    redis = FakeRedis()
    roster.load_persisted_external_witness_roster(
        db,
        redis_client=redis,
    )
    original_state = dict(db.state["trust_state"])
    original_state_sha = db.state["state_sha256"]

    enable_rotation_target(monkeypatch)
    checkpoint_receipt = roster.persist_checkpoint(
        original_state,
        auth_key_id="roster-b-2026-09",
        redis_client=redis,
    )
    assert checkpoint_receipt["mode"] == "refreshed"
    assert db.state["storage_auth_key_id"] == "roster-a"

    receipt = roster.rotate_storage_authentication(
        db,
        redis_client=redis,
    )

    assert receipt["status"] == "verified"
    assert receipt["state_preserved"] is True
    assert db.state["storage_auth_key_id"] == "roster-b-2026-09"
    assert db.state["state_sha256"] == original_state_sha
    assert roster.read_checkpoint(
        redis_client=redis
    )["authKeyId"] == "roster-b-2026-09"


def test_load_auto_rotates_when_target_is_staged(monkeypatch):
    db = FakeDB()
    redis = FakeRedis()
    roster.load_persisted_external_witness_roster(
        db,
        redis_client=redis,
    )

    enable_rotation_target(monkeypatch)
    loaded = roster.load_persisted_external_witness_roster(
        db,
        redis_client=redis,
    )

    assert loaded["roster_storage_rotation_supported"] is True
    assert loaded["roster_storage_rotation_mode"] == "rotated"
    assert loaded["roster_storage_auth_key_id"] == "roster-b-2026-09"


def test_active_key_can_flip_after_verified_rotation(monkeypatch):
    db = FakeDB()
    redis = FakeRedis()
    roster.load_persisted_external_witness_roster(
        db,
        redis_client=redis,
    )
    enable_rotation_target(monkeypatch)
    roster.rotate_storage_authentication(
        db,
        redis_client=redis,
    )

    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_ACTIVE_KEY_ID",
        "roster-b-2026-09",
    )
    loaded = roster.load_persisted_external_witness_roster(
        db,
        redis_client=redis,
    )

    assert loaded["roster_storage_auth_key_id"] == "roster-b-2026-09"
    assert loaded["roster_storage_rotation_mode"] == "not-needed"


def test_rotation_target_without_overlap_secret_fails(monkeypatch):
    db = FakeDB()
    redis = FakeRedis()
    roster.load_persisted_external_witness_roster(
        db,
        redis_client=redis,
    )
    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_ROTATION_TARGET_KEY_ID",
        "roster-b-2026-09",
    )
    monkeypatch.delenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_ROTATION_TARGET_SECRET",
        raising=False,
    )

    with pytest.raises(
        roster.ExternalWitnessRosterError,
        match="external-witness-roster-storage-rotation-target-invalid",
    ):
        roster.rotate_storage_authentication(
            db,
            redis_client=redis,
        )
