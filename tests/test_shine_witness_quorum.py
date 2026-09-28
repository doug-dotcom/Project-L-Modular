import json

import pytest

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


class FakeRedis:
    def __init__(self):
        self.rows = {}

    def hgetall(self, key):
        return dict(self.rows.get(key, {}))

    def eval(self, _script, _numkeys, key, *args):
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

    result = quorum.ensure_trust_witness_quorum(
        object(),
        {"state": "unused"},
    )

    assert result["status"] == "verified"
    assert result["minimum_witnesses"] == 2
    assert result["verified_witness_count"] == 2
    assert result["witness_ids"] == [
        "foundation-project-l",
        "redis-project-l",
    ]
    assert result["policy_sha256"] == POLICY_SHA
    assert result["independence"] == [
        "foundation-supabase",
        "railway-redis-volume",
    ]
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
            object(),
            {"state": "unused"},
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
            object(),
            {"state": "unused"},
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
            object(),
            {"state": "unused"},
        )
