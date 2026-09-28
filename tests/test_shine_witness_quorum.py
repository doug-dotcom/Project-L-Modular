import json

import pytest

from services import foundation_chain_redis_checkpoint as chain_redis
from services import shine_witness_quorum as quorum


POLICY_SHA = "26b6d1a3b4183cfa596f8c9c06c18e73aa0eda6a80a6362649130e9357bf220e"
HEAD = {
    "headVersion": 1,
    "headType": "decision_trace_trust_state_monotonic_head",
    "authAlgorithm": "HMAC-SHA-256",
    "authKeyId": "storage-a",
    "checkpointChainVersion": 1,
    "sequence": 7,
    "checkpointSha256": "1" * 64,
    "generation": 2,
    "keyset_sha256": "2" * 64,
    "stateSha256": "3" * 64,
    "headSha256": "4" * 64,
    "authTag": "5" * 64,
}


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakePolicyDB:
    def __init__(
        self,
        state=None,
        *,
        inconsistent_reason=None,
        storage=None,
    ):
        self.state = state
        self.inconsistent_reason = inconsistent_reason
        self.storage = storage
        self.rpc_calls = []

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        db = self

        class Call:
            def execute(self):
                if name in {
                    "shine_ai_witness_quorum_policy_snapshot_v1",
                    "shine_ai_witness_quorum_policy_snapshot_v2",
                }:
                    if db.inconsistent_reason:
                        return FakeResult({
                            "status": "inconsistent",
                            "reason_code": db.inconsistent_reason,
                        })
                    if db.state is None:
                        return FakeResult({"status": "unbootstrapped"})
                    payload = {
                        "status": "trusted",
                        "trust_state": dict(db.state),
                    }
                    if name.endswith("_v2"):
                        if db.storage is None:
                            payload.update({
                                "status": "unsealed",
                                "reason_code":
                                    "witness-quorum-policy-storage-authentication-missing",
                            })
                        else:
                            payload.update(dict(db.storage))
                    return FakeResult(payload)

                if name == "shine_ai_witness_quorum_policy_bootstrap_v1":
                    db.state = {
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
                    return FakeResult({
                        "status": "trusted",
                        "trust_state": dict(db.state),
                    })

                if name == "shine_ai_witness_quorum_policy_bootstrap_v2":
                    if db.state is None:
                        db.state = {
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
                    db.storage = {
                        "state_sha256": params["p_state_sha256"],
                        "storage_auth_key_id":
                            params["p_storage_auth_key_id"],
                        "storage_auth_tag": params["p_storage_auth_tag"],
                    }
                    return FakeResult({
                        "status": "trusted",
                        "trust_state": dict(db.state),
                    })

                if name == "shine_ai_witness_quorum_policy_seal_v2":
                    assert db.state is not None
                    assert (
                        db.state["generation"]
                        == params["p_expected_generation"]
                    )
                    assert (
                        db.state["policySha256"]
                        == params["p_expected_policy_sha256"]
                    )
                    db.storage = {
                        "state_sha256": params["p_state_sha256"],
                        "storage_auth_key_id":
                            params["p_storage_auth_key_id"],
                        "storage_auth_tag": params["p_storage_auth_tag"],
                    }
                    return FakeResult({
                        "status": "sealed",
                        "generation": db.state["generation"],
                        "policy_sha256": db.state["policySha256"],
                    })

                if name == "shine_ai_witness_quorum_policy_rotate_storage_v2":
                    assert db.state is not None
                    assert db.storage is not None
                    assert (
                        db.state["generation"]
                        == params["p_expected_generation"]
                    )
                    assert (
                        db.state["policySha256"]
                        == params["p_expected_policy_sha256"]
                    )
                    assert (
                        db.storage["state_sha256"]
                        == params["p_expected_state_sha256"]
                    )
                    current_key = db.storage["storage_auth_key_id"]
                    target_key = params["p_target_auth_key_id"]
                    if current_key != target_key:
                        assert (
                            current_key
                            == params["p_source_envelope_auth_key_id"]
                        )
                    db.storage["storage_auth_key_id"] = target_key
                    db.storage["storage_auth_tag"] = params[
                        "p_storage_auth_tag"
                    ]
                    return FakeResult({
                        "status": "rotated",
                        "generation": db.state["generation"],
                        "policy_sha256": db.state["policySha256"],
                        "storage_auth_key_id": target_key,
                    })

                raise AssertionError(name)

        return Call()


class FakeRedis:
    def __init__(self):
        self.rows = {}

    def hgetall(self, key):
        return dict(self.rows.get(key, {}))

    def eval(self, _script, _numkeys, key, *args):
        if key == chain_redis.REDIS_KEY:
            sequence, previous, chain_tag, checkpoint_json = args
            sequence = int(sequence)
            current = self.rows.get(key)
            if current is None:
                if sequence != 1 or previous != "0" * 64:
                    return ["genesis-invalid"]
                self.rows[key] = {
                    "sequence": str(sequence),
                    "previous_chain_tag": previous,
                    "chain_tag": chain_tag,
                    "checkpoint_json": checkpoint_json,
                }
                return ["created"]
            current_sequence = int(current["sequence"])
            if sequence < current_sequence:
                return ["rollback"]
            if sequence == current_sequence:
                if (
                    previous == current["previous_chain_tag"]
                    and chain_tag == current["chain_tag"]
                ):
                    return ["existing"]
                return ["equivocation"]
            if sequence != current_sequence + 1:
                return ["sequence-gap"]
            if previous != current["chain_tag"]:
                return ["predecessor-mismatch"]
            self.rows[key] = {
                "sequence": str(sequence),
                "previous_chain_tag": previous,
                "chain_tag": chain_tag,
                "checkpoint_json": checkpoint_json,
            }
            return ["advanced"]

        if len(args) == 4:
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
            current["checkpoint_json"] = checkpoint_json
            return ["refreshed"]

        (
            sequence,
            head_sha,
            generation,
            keyset_sha,
            state_sha,
            witness_json,
        ) = args
        sequence = int(sequence)
        generation = int(generation)
        current = self.rows.get(key)
        if current is None:
            if sequence != 1 and sequence != HEAD["sequence"]:
                return ["genesis-invalid"]
            self.rows[key] = {
                "sequence": str(sequence),
                "head_sha256": head_sha,
                "generation": str(generation),
                "keyset_sha256": keyset_sha,
                "state_sha256": state_sha,
                "witness_json": witness_json,
            }
            return ["created"]

        current_sequence = int(current["sequence"])
        if sequence < current_sequence:
            return ["rollback"]
        if sequence == current_sequence:
            if (
                current["head_sha256"] == head_sha
                and int(current["generation"]) == generation
                and current["keyset_sha256"] == keyset_sha
                and current["state_sha256"] == state_sha
            ):
                return ["existing"]
            return ["equivocation"]
        if sequence != current_sequence + 1:
            return ["sequence-gap"]
        self.rows[key] = {
            "sequence": str(sequence),
            "head_sha256": head_sha,
            "generation": str(generation),
            "keyset_sha256": keyset_sha,
            "state_sha256": state_sha,
            "witness_json": witness_json,
        }
        return ["advanced"]


@pytest.fixture(autouse=True)
def quorum_env(monkeypatch):
    monkeypatch.setenv(
        "SHINE_TRACE_REDIS_WITNESS_KEYRING_JSON",
        json.dumps({
            "redis-witness-a": "R" * 48,
            "redis-witness-b": "S" * 48,
        }),
    )
    monkeypatch.setenv(
        "SHINE_TRACE_REDIS_WITNESS_ACTIVE_KEY_ID",
        "redis-witness-a",
    )
    monkeypatch.setenv(
        "SHINE_TRACE_WITNESS_QUORUM_POLICY_STORAGE_KEYRING_JSON",
        json.dumps({
            "policy-a": "P" * 48,
            "policy-b": "Q" * 48,
        }),
    )
    monkeypatch.setenv(
        "SHINE_TRACE_WITNESS_QUORUM_POLICY_STORAGE_ACTIVE_KEY_ID",
        "policy-a",
    )
    monkeypatch.setenv(
        chain_redis.KEYRING_ENV,
        json.dumps({
            "foundation-chain-redis-a": "C" * 48,
            "foundation-chain-redis-b": "D" * 48,
        }),
    )
    monkeypatch.setenv(
        chain_redis.ACTIVE_KEY_ENV,
        "foundation-chain-redis-a",
    )
    monkeypatch.setenv(
        "SHINE_TRACE_WITNESS_QUORUM_POLICY_JSON",
        json.dumps({
            "policyVersion": 1,
            "policyType":
                "decision_trace_trust_state_witness_quorum_policy",
            "generation": 1,
            "minimumWitnesses": 2,
            "acceptedWitnessIds": [
                "foundation-project-l",
                "redis-project-l",
            ],
            "previousPolicySha256": None,
            "policySha256": POLICY_SHA,
        }),
    )
    monkeypatch.setattr(
        quorum,
        "load_persisted_external_witness_roster",
        lambda *_args, **_kwargs: {
            "policyVersion": 1,
            "policyType":
                "decision_trace_trust_state_witness_quorum_policy_external_head_witness_quorum_policy",
            "generation": 1,
            "minimumWitnesses": 2,
            "acceptedWitnessIds": [
                "foundation-project-l",
                "redis-project-l",
            ],
            "previousPolicySha256": None,
            "policySha256":
                "a5c456d49e47f1be3f2a7b7ed017328844484ba05c4e6ef3212412c6361156c4",
            "roster_trust_persisted": True,
            "roster_trust_source": "project-l-supabase",
            "roster_storage_authenticated": True,
            "roster_storage_auth_key_id": "roster-a",
            "roster_storage_state_sha256": "1" * 64,
            "roster_storage_checkpoint_independent": True,
            "roster_storage_checkpoint_retention":
                "railway-redis-volume",
        },
    )


def redis_receipt():
    return {
        "status": "verified",
        "witness_id": "redis-project-l",
        "sequence": HEAD["sequence"],
        "head_sha256": HEAD["headSha256"],
        "generation": HEAD["generation"],
        "keyset_sha256": HEAD["keyset_sha256"],
        "state_sha256": HEAD["stateSha256"],
        "auth_key_id": "redis-witness-a",
        "mode": "existing",
        "independent_retention": "railway-redis-volume",
    }


def foundation_receipt():
    return {
        "status": "verified",
        "witness_id": "foundation-project-l",
        "sequence": HEAD["sequence"],
        "head_sha256": HEAD["headSha256"],
        "generation": HEAD["generation"],
        "keyset_sha256": HEAD["keyset_sha256"],
        "state_sha256": HEAD["stateSha256"],
        "auth_key_id": "foundation-witness-v1",
        "mode": "existing-witness",
        "independent_retention": "foundation-supabase",
        "history_status": "verified",
        "chain_version": 1,
        "previous_chain_tag": "6" * 64,
        "chain_tag": "7" * 64,
    }


def test_policy_is_exact_fixed_two_of_two():
    policy = quorum.load_quorum_policy()

    assert policy["generation"] == 1
    assert policy["minimumWitnesses"] == 2
    assert policy["acceptedWitnessIds"] == [
        "foundation-project-l",
        "redis-project-l",
    ]
    assert policy["policySha256"] == POLICY_SHA



def test_persisted_policy_bootstraps_from_certified_deployment_pin():
    db = FakePolicyDB()
    redis = FakeRedis()

    value = quorum.load_persisted_quorum_policy(
        db,
        redis_client=redis,
    )

    assert value["generation"] == 1
    assert value["minimumWitnesses"] == 2
    assert value["acceptedWitnessIds"] == [
        "foundation-project-l",
        "redis-project-l",
    ]
    assert value["policySha256"] == POLICY_SHA
    assert value["policy_trust_persisted"] is True
    assert value["policy_trust_source"] == "project-l-supabase"
    assert value["policy_trust_generation"] == 1
    assert value["policy_storage_authenticated"] is True
    assert value["policy_storage_auth_key_id"] == "policy-a"
    assert value["policy_storage_checkpoint_independent"] is True
    assert value["policy_storage_checkpoint_retention"] == "railway-redis-volume"
    assert db.state["policySha256"] == POLICY_SHA
    assert db.storage is not None
    assert [name for name, _params in db.rpc_calls] == [
        "shine_ai_witness_quorum_policy_snapshot_v2",
        "shine_ai_witness_quorum_policy_bootstrap_v2",
        "shine_ai_witness_quorum_policy_snapshot_v2",
    ]


def test_persisted_policy_rejects_same_generation_deployment_fork(
    monkeypatch,
):
    db = FakePolicyDB({
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
    })
    fork = {
        "policyVersion": 1,
        "policyType":
            "decision_trace_trust_state_witness_quorum_policy",
        "generation": 1,
        "minimumWitnesses": 2,
        "acceptedWitnessIds": [
            "foundation-project-l",
            "redis-project-l",
        ],
        "previousPolicySha256": None,
        "policySha256": "0" * 64,
    }
    monkeypatch.setenv(
        "SHINE_TRACE_WITNESS_QUORUM_POLICY_JSON",
        json.dumps(fork),
    )

    with pytest.raises(
        quorum.WitnessQuorumError,
        match="policy-digest-mismatch",
    ):
        quorum.load_persisted_quorum_policy(
            db,
            redis_client=FakeRedis(),
        )


def test_persisted_policy_refuses_uncertified_future_state():
    db = FakePolicyDB({
        "trustStateVersion": 1,
        "trustStateType":
            "decision_trace_trust_state_witness_quorum_policy",
        "generation": 2,
        "minimumWitnesses": 2,
        "acceptedWitnessIds": [
            "foundation-project-l",
            "redis-project-l",
        ],
        "previousPolicySha256": POLICY_SHA,
        "policySha256": "1" * 64,
    })

    with pytest.raises(
        quorum.WitnessQuorumError,
        match="policy",
    ):
        quorum.load_persisted_quorum_policy(
            db,
            redis_client=FakeRedis(),
        )


def test_persisted_policy_storage_inconsistency_fails_closed():
    db = FakePolicyDB(
        inconsistent_reason="witness-quorum-policy-high-water-mismatch"
    )

    with pytest.raises(
        quorum.WitnessQuorumError,
        match="high-water-mismatch",
    ):
        quorum.load_persisted_quorum_policy(
            db,
            redis_client=FakeRedis(),
        )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda p: p.update({"minimumWitnesses": 1}),
        lambda p: p.update({"acceptedWitnessIds": ["foundation-project-l"]}),
        lambda p: p.update({
            "acceptedWitnessIds": [
                "foundation-project-l",
                "foundation-project-l",
            ]
        }),
        lambda p: p.update({"generation": 2}),
        lambda p: p.update({"policySha256": "0" * 64}),
    ],
)
def test_policy_downgrade_or_fork_fails_closed(monkeypatch, mutator):
    policy = {
        "policyVersion": 1,
        "policyType":
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
    mutator(policy)
    monkeypatch.setenv(
        "SHINE_TRACE_WITNESS_QUORUM_POLICY_JSON",
        json.dumps(policy),
    )

    with pytest.raises(
        quorum.WitnessQuorumError,
        match="trust-witness-quorum-policy",
    ):
        quorum.load_quorum_policy()


def test_redis_witness_hmac_detects_tampering():
    witness = quorum.create_redis_witness(
        HEAD,
        auth_key_id="redis-witness-a",
    )
    assert quorum.verify_witness(
        witness,
        expected_witness_id="redis-project-l",
        secret_resolver=quorum._redis_witness_secret,
    )["headSha256"] == HEAD["headSha256"]

    witness["stateSha256"] = "9" * 64
    with pytest.raises(
        quorum.WitnessQuorumError,
        match="trust-witness-auth-failed",
    ):
        quorum.verify_witness(
            witness,
            expected_witness_id="redis-project-l",
            secret_resolver=quorum._redis_witness_secret,
        )


def test_redis_witness_is_persisted_and_idempotent(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(
        quorum,
        "prepare_monotonic_head",
        lambda *_args, **_kwargs: {
            "status": "ready",
            "mode": "existing-head",
            "head": HEAD,
        },
    )

    first = quorum.ensure_redis_trust_witness(
        {"unused": True},
        redis_client=redis,
    )
    second = quorum.ensure_redis_trust_witness(
        {"unused": True},
        redis_client=redis,
    )

    assert first["mode"] == "created"
    assert second["mode"] == "existing"
    assert second["witness_id"] == "redis-project-l"
    stored = quorum.read_redis_witness(redis_client=redis)
    assert stored["sequence"] == HEAD["sequence"]
    assert stored["headSha256"] == HEAD["headSha256"]


def test_quorum_requires_two_distinct_matching_witnesses(monkeypatch):
    monkeypatch.setattr(
        quorum,
        "ensure_redis_trust_witness",
        lambda *_args, **_kwargs: redis_receipt(),
    )
    monkeypatch.setattr(
        quorum,
        "ensure_foundation_trust_witness",
        lambda *_args, **_kwargs: foundation_receipt(),
    )
    checkpoint_receipt = {
        "status": "verified",
        "checkpoint_version": 1,
        "witness_id": "foundation-project-l",
        "chain_version": 1,
        "sequence": HEAD["sequence"],
        "previous_chain_tag": "6" * 64,
        "chain_tag": "7" * 64,
        "auth_key_id": "project-l-foundation-chain-checkpoint-v1",
        "storage": "project-l-supabase-vault-hmac",
        "ledger_rows": HEAD["sequence"],
        "mode": "existing",
    }
    monkeypatch.setattr(
        quorum,
        "ensure_foundation_chain_checkpoint",
        lambda *_args, **_kwargs: checkpoint_receipt,
    )
    redis_checkpoint_receipt = {
        "status": "verified",
        "checkpoint_version": 1,
        "witness_id": "foundation-project-l",
        "chain_version": 1,
        "sequence": HEAD["sequence"],
        "previous_chain_tag": "6" * 64,
        "chain_tag": "7" * 64,
        "auth_key_id": "foundation-chain-redis-a",
        "storage": "railway-redis-volume",
        "mode": "existing",
    }
    monkeypatch.setattr(
        quorum,
        "ensure_redis_foundation_chain_checkpoint",
        lambda *_args, **_kwargs: redis_checkpoint_receipt,
    )

    result = quorum.ensure_trust_witness_quorum(
        FakePolicyDB(),
        {"state": "unused"},
        redis_client=FakeRedis(),
    )

    assert result["status"] == "verified"
    assert result["minimum_witnesses"] == 2
    assert result["verified_witness_count"] == 2
    assert result["witness_ids"] == [
        "foundation-project-l",
        "redis-project-l",
    ]
    assert result["policy_sha256"] == POLICY_SHA
    assert result["policy_trust_persisted"] is True
    assert result["policy_trust_source"] == "project-l-supabase"
    assert result["policy_trust_generation"] == 1
    assert result["policy_storage_authenticated"] is True
    assert result["policy_storage_auth_key_id"] == "policy-a"
    assert result["policy_storage_checkpoint_independent"] is True
    assert result["independence"] == [
        "foundation-supabase",
        "railway-redis-volume",
    ]
    assert result["foundation_chain"] == {
        "status": "verified",
        "witness_id": "foundation-project-l",
        "chain_version": 1,
        "sequence": HEAD["sequence"],
        "previous_chain_tag": "6" * 64,
        "chain_tag": "7" * 64,
    }
    assert result["foundation_chain_checkpoint"] == checkpoint_receipt
    assert (
        result["foundation_chain_redis_checkpoint"]
        == redis_checkpoint_receipt
    )
    assert result["foundation_chain_checkpoint_redundancy"] == {
        "status": "verified",
        "witness_id": "foundation-project-l",
        "chain_version": 1,
        "sequence": HEAD["sequence"],
        "previous_chain_tag": "6" * 64,
        "chain_tag": "7" * 64,
        "verified_store_count": 2,
        "stores": [
            "project-l-supabase-vault-hmac",
            "railway-redis-volume",
        ],
    }
    assert "authTag" not in json.dumps(result)


def test_quorum_rejects_head_disagreement(monkeypatch):
    foundation = foundation_receipt()
    foundation["state_sha256"] = "8" * 64
    monkeypatch.setattr(
        quorum,
        "ensure_redis_trust_witness",
        lambda *_args, **_kwargs: redis_receipt(),
    )
    monkeypatch.setattr(
        quorum,
        "ensure_foundation_trust_witness",
        lambda *_args, **_kwargs: foundation,
    )

    with pytest.raises(
        quorum.WitnessQuorumError,
        match="trust-witness-quorum-disagreement",
    ):
        quorum.ensure_trust_witness_quorum(
            FakePolicyDB(),
            {"state": "unused"},
            redis_client=FakeRedis(),
        )


def test_quorum_rejects_duplicate_or_unapproved_witness(monkeypatch):
    duplicate = foundation_receipt()
    duplicate["witness_id"] = "redis-project-l"
    monkeypatch.setattr(
        quorum,
        "ensure_redis_trust_witness",
        lambda *_args, **_kwargs: redis_receipt(),
    )
    monkeypatch.setattr(
        quorum,
        "ensure_foundation_trust_witness",
        lambda *_args, **_kwargs: duplicate,
    )

    with pytest.raises(
        quorum.WitnessQuorumError,
        match="trust-witness-quorum-invalid-member",
    ):
        quorum.ensure_trust_witness_quorum(
            FakePolicyDB(),
            {"state": "unused"},
            redis_client=FakeRedis(),
        )


def test_quorum_fails_when_foundation_witness_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        quorum,
        "ensure_redis_trust_witness",
        lambda *_args, **_kwargs: redis_receipt(),
    )

    def fail(*_args, **_kwargs):
        raise quorum.FoundationWitnessError("foundation-witness-unavailable")

    monkeypatch.setattr(
        quorum,
        "ensure_foundation_trust_witness",
        fail,
    )

    with pytest.raises(
        quorum.WitnessQuorumError,
        match="foundation-witness-unavailable",
    ):
        quorum.ensure_trust_witness_quorum(
            FakePolicyDB(),
            {"state": "unused"},
            redis_client=FakeRedis(),
        )



@pytest.mark.parametrize(
    "field,value",
    [
        ("history_status", "unavailable"),
        ("chain_version", 2),
        ("previous_chain_tag", "bad"),
        ("chain_tag", "bad"),
    ],
)
def test_quorum_rejects_unverified_foundation_chain(
    monkeypatch,
    field,
    value,
):
    foundation = foundation_receipt()
    foundation[field] = value

    monkeypatch.setattr(
        quorum,
        "ensure_redis_trust_witness",
        lambda *_args, **_kwargs: redis_receipt(),
    )
    monkeypatch.setattr(
        quorum,
        "ensure_foundation_trust_witness",
        lambda *_args, **_kwargs: foundation,
    )

    with pytest.raises(
        quorum.WitnessQuorumError,
        match="trust-witness-foundation-chain-invalid",
    ):
        quorum.ensure_trust_witness_quorum(
            FakePolicyDB(),
            {"state": "unused"},
            redis_client=FakeRedis(),
        )



def test_quorum_fails_closed_when_chain_checkpoint_rejects(monkeypatch):
    monkeypatch.setattr(
        quorum,
        "ensure_redis_trust_witness",
        lambda *_args, **_kwargs: redis_receipt(),
    )
    monkeypatch.setattr(
        quorum,
        "ensure_foundation_trust_witness",
        lambda *_args, **_kwargs: foundation_receipt(),
    )

    def fail(*_args, **_kwargs):
        raise quorum.FoundationChainCheckpointError(
            "foundation-chain-checkpoint-ahead"
        )

    monkeypatch.setattr(
        quorum,
        "ensure_foundation_chain_checkpoint",
        fail,
    )

    with pytest.raises(
        quorum.WitnessQuorumError,
        match="foundation-chain-checkpoint-ahead",
    ):
        quorum.ensure_trust_witness_quorum(
            FakePolicyDB(),
            {"state": "unused"},
            redis_client=FakeRedis(),
        )



def test_persisted_policy_storage_rotates_without_changing_policy(monkeypatch):
    db = FakePolicyDB()
    redis = FakeRedis()

    first = quorum.load_persisted_quorum_policy(
        db,
        redis_client=redis,
    )
    original_state = dict(db.state)
    original_state_sha = first["policy_storage_state_sha256"]

    monkeypatch.setenv(
        "SHINE_TRACE_WITNESS_QUORUM_POLICY_STORAGE_ACTIVE_KEY_ID",
        "policy-b",
    )
    second = quorum.load_persisted_quorum_policy(
        db,
        redis_client=redis,
    )

    assert second["policy_storage_auth_key_id"] == "policy-b"
    assert second["policy_storage_state_sha256"] == original_state_sha
    assert second["generation"] == first["generation"] == 1
    assert second["minimumWitnesses"] == first["minimumWitnesses"] == 2
    assert second["acceptedWitnessIds"] == first["acceptedWitnessIds"]
    assert second["policySha256"] == first["policySha256"] == POLICY_SHA
    assert db.state == original_state
    assert db.storage["storage_auth_key_id"] == "policy-b"
    assert second["policy_storage_rotation"]["target_auth_key_id"] == "policy-b"



def test_quorum_fails_closed_when_redis_chain_checkpoint_rejects(
    monkeypatch,
):
    monkeypatch.setattr(
        quorum,
        "ensure_redis_trust_witness",
        lambda *_args, **_kwargs: redis_receipt(),
    )
    monkeypatch.setattr(
        quorum,
        "ensure_foundation_trust_witness",
        lambda *_args, **_kwargs: foundation_receipt(),
    )
    monkeypatch.setattr(
        quorum,
        "ensure_foundation_chain_checkpoint",
        lambda *_args, **_kwargs: {
            "status": "verified",
            "checkpoint_version": 1,
            "witness_id": "foundation-project-l",
            "chain_version": 1,
            "sequence": HEAD["sequence"],
            "previous_chain_tag": "6" * 64,
            "chain_tag": "7" * 64,
            "storage": "project-l-supabase-vault-hmac",
            "mode": "existing",
        },
    )

    def fail(*_args, **_kwargs):
        raise quorum.RedisFoundationChainCheckpointError(
            "foundation-chain-redis-ahead"
        )

    monkeypatch.setattr(
        quorum,
        "ensure_redis_foundation_chain_checkpoint",
        fail,
    )

    with pytest.raises(
        quorum.WitnessQuorumError,
        match="foundation-chain-redis-ahead",
    ):
        quorum.ensure_trust_witness_quorum(
            FakePolicyDB(),
            {"state": "unused"},
            redis_client=FakeRedis(),
        )


def test_quorum_rejects_checkpoint_store_disagreement(monkeypatch):
    monkeypatch.setattr(
        quorum,
        "ensure_redis_trust_witness",
        lambda *_args, **_kwargs: redis_receipt(),
    )
    monkeypatch.setattr(
        quorum,
        "ensure_foundation_trust_witness",
        lambda *_args, **_kwargs: foundation_receipt(),
    )
    monkeypatch.setattr(
        quorum,
        "ensure_foundation_chain_checkpoint",
        lambda *_args, **_kwargs: {
            "status": "verified",
            "checkpoint_version": 1,
            "witness_id": "foundation-project-l",
            "chain_version": 1,
            "sequence": HEAD["sequence"],
            "previous_chain_tag": "6" * 64,
            "chain_tag": "7" * 64,
            "storage": "project-l-supabase-vault-hmac",
            "mode": "existing",
        },
    )
    monkeypatch.setattr(
        quorum,
        "ensure_redis_foundation_chain_checkpoint",
        lambda *_args, **_kwargs: {
            "status": "verified",
            "checkpoint_version": 1,
            "witness_id": "foundation-project-l",
            "chain_version": 1,
            "sequence": HEAD["sequence"],
            "previous_chain_tag": "6" * 64,
            "chain_tag": "8" * 64,
            "storage": "railway-redis-volume",
            "mode": "existing",
        },
    )

    with pytest.raises(
        quorum.WitnessQuorumError,
        match="trust-witness-foundation-chain-checkpoint-disagreement",
    ):
        quorum.ensure_trust_witness_quorum(
            FakePolicyDB(),
            {"state": "unused"},
            redis_client=FakeRedis(),
        )



def test_quorum_rejects_external_roster_policy_mismatch(monkeypatch):
    monkeypatch.setattr(
        quorum,
        "load_persisted_external_witness_roster",
        lambda *_args, **_kwargs: {
            "generation": 1,
            "minimumWitnesses": 2,
            "acceptedWitnessIds": [
                "foundation-project-l",
                "other-witness",
            ],
            "policySha256": "a" * 64,
            "roster_trust_persisted": True,
            "roster_trust_source": "project-l-supabase",
            "roster_storage_authenticated": True,
            "roster_storage_auth_key_id": "roster-a",
            "roster_storage_state_sha256": "b" * 64,
            "roster_storage_checkpoint_independent": True,
            "roster_storage_checkpoint_retention":
                "railway-redis-volume",
        },
    )

    with pytest.raises(
        quorum.WitnessQuorumError,
        match="trust-witness-external-roster-policy-mismatch",
    ):
        quorum.ensure_trust_witness_quorum(
            FakePolicyDB(),
            {"state": "unused"},
            redis_client=FakeRedis(),
        )
