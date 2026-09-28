import pytest

from services import shine_witness_quorum_policy as policy


EXPECTED_GENESIS_SHA256 = (
    "aac7d1acaec5bf64d5f7d3fe535cbb48"
    "e99df0900eb91e8a8b44cbbfcbb5a92e"
)


def foundation_witness():
    return {
        "status": "verified",
        "witness_id": "foundation-project-l",
        "sequence": 7,
        "head_sha256": "a" * 64,
        "generation": 3,
        "keyset_sha256": "b" * 64,
        "state_sha256": "c" * 64,
    }


def redis_witness():
    return {
        "status": "verified",
        "witness_id": "project-l-redis",
        "sequence": 7,
        "head_sha256": "a" * 64,
        "generation": 3,
        "keyset_sha256": "b" * 64,
        "state_sha256": "c" * 64,
    }


def test_genesis_policy_matches_shine_ai_layer149_canonical_vector():
    value = policy.genesis_policy()

    assert value == {
        "policyVersion": 1,
        "policyType": (
            "decision_trace_trust_state_witness_quorum_policy"
        ),
        "generation": 1,
        "minimumWitnesses": 2,
        "acceptedWitnessIds": [
            "foundation-project-l",
            "project-l-redis",
        ],
        "previousPolicySha256": None,
        "policySha256": EXPECTED_GENESIS_SHA256,
    }
    assert policy.digest_policy_material(value) == EXPECTED_GENESIS_SHA256


def test_genesis_policy_trust_state_is_exact_and_canonical():
    state = policy.genesis_policy_trust_state()

    assert state["trustStateVersion"] == 1
    assert state["generation"] == 1
    assert state["minimumWitnesses"] == 2
    assert state["acceptedWitnessIds"] == [
        "foundation-project-l",
        "project-l-redis",
    ]
    assert state["policySha256"] == EXPECTED_GENESIS_SHA256
    assert policy.project_policy_trust_state({
        **state,
        "untrustedAdditiveField": "drop-me",
    }) == state


def test_quorum_requires_both_accepted_witnesses():
    state = policy.genesis_policy_trust_state()

    result = policy.evaluate_witness_quorum(
        state,
        foundation_witness=foundation_witness(),
        local_witness=redis_witness(),
    )
    assert result["status"] == "verified"
    assert result["minimum_witnesses"] == 2
    assert result["verified_count"] == 2
    assert result["verified_witness_ids"] == [
        "foundation-project-l",
        "project-l-redis",
    ]

    with pytest.raises(
        policy.WitnessQuorumPolicyError,
        match="witness-quorum-insufficient",
    ):
        policy.evaluate_witness_quorum(
            state,
            foundation_witness=foundation_witness(),
            local_witness={},
        )


def test_quorum_rejects_two_witnesses_over_different_heads():
    state = policy.genesis_policy_trust_state()
    local = redis_witness()
    local["head_sha256"] = "d" * 64

    with pytest.raises(
        policy.WitnessQuorumPolicyError,
        match="witness-quorum-head-mismatch",
    ):
        policy.evaluate_witness_quorum(
            state,
            foundation_witness=foundation_witness(),
            local_witness=local,
        )


def test_policy_fingerprint_rejects_membership_or_threshold_drift():
    value = policy.genesis_policy()
    value["minimumWitnesses"] = 1

    with pytest.raises(
        policy.WitnessQuorumPolicyError,
        match="witness-quorum-policy-invalid",
    ):
        policy.project_policy(value)

    value = policy.genesis_policy()
    value["acceptedWitnessIds"] = [
        "foundation-project-l",
        "project-l-other",
    ]
    with pytest.raises(
        policy.WitnessQuorumPolicyError,
        match="witness-quorum-policy-fingerprint-invalid",
    ):
        policy.project_policy(value)
