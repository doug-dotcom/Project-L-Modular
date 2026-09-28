import json

import pytest

from services import foundation_trust_witness as witness


HEAD = {
    "headVersion": 1,
    "headType":
        "decision_trace_trust_state_witness_quorum_policy_"
        "external_head_witness_quorum_monotonic_head",
    "checkpointChainVersion": 1,
    "sequence": 1,
    "checkpointSha256": "a" * 64,
    "generation": 1,
    "policySha256": "b" * 64,
    "stateSha256": "c" * 64,
    "headSha256": "d" * 64,
}


class Result:
    def __init__(self, data):
        self.data = data


class DB:
    def rpc(self, name, params):
        assert name == "concierge_foundation_client_token_v1"
        assert params == {}

        class Call:
            def execute(self):
                return Result("t" * 48)

        return Call()


class Response:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {
            "content-length": str(len(self.content)),
        }

    def json(self):
        return self._payload


def receipt(**overrides):
    value = {
        "status": "witnessed",
        "witnessVersion": 1,
        "witnessType":
            "decision_trace_trust_state_witness_quorum_policy_"
            "external_head_witness_quorum_monotonic_head_witness",
        "authAlgorithm": "HMAC-SHA-256",
        "witnessId": "foundation-project-l-roster-head",
        "authKeyId": "foundation-roster-head-witness-v1",
        "headVersion": 1,
        "sequence": HEAD["sequence"],
        "headSha256": HEAD["headSha256"],
        "generation": HEAD["generation"],
        "policySha256": HEAD["policySha256"],
        "stateSha256": HEAD["stateSha256"],
        "authTag": "e" * 64,
    }
    value.update(overrides)
    return value


def test_roster_head_witness_genesis_is_created_with_bounded_payload():
    gets = []
    posts = []

    def fake_get(url, **kwargs):
        gets.append((url, kwargs))
        return Response({
            "status": "empty",
            "witnessId": "foundation-project-l-roster-head",
        })

    def fake_post(url, **kwargs):
        posts.append((url, kwargs))
        payload = kwargs["json"]
        assert payload == {
            "scope": "external-roster-head",
            "witnessId": "foundation-project-l-roster-head",
            "sequence": 1,
            "headSha256": "d" * 64,
            "generation": 1,
            "policySha256": "b" * 64,
            "stateSha256": "c" * 64,
        }
        return Response(receipt())

    result = witness.ensure_foundation_roster_head_witness(
        DB(),
        HEAD,
        get_impl=fake_get,
        post_impl=fake_post,
    )

    assert result["status"] == "verified"
    assert result["mode"] == "created"
    assert result["independent_retention"] == "foundation-supabase"
    assert result["head_sha256"] == HEAD["headSha256"]
    assert result["witness_id"] == "foundation-project-l-roster-head"
    assert gets[0][1]["params"]["scope"] == "external-roster-head"
    assert "auth_tag" in result
    assert len(posts) == 1


def test_roster_head_witness_existing_exact_head_is_idempotent():
    result = witness.ensure_foundation_roster_head_witness(
        DB(),
        HEAD,
        get_impl=lambda *_args, **_kwargs: Response(receipt()),
        post_impl=lambda *_args, **_kwargs: (
            _ for _ in ()
        ).throw(AssertionError("exact head must not post")),
    )

    assert result["status"] == "verified"
    assert result["mode"] == "existing-witness"


def test_roster_head_witness_rejects_local_rollback_when_foundation_is_ahead():
    ahead = receipt(
        sequence=2,
        generation=2,
        headSha256="1" * 64,
        policySha256="2" * 64,
        stateSha256="3" * 64,
    )

    with pytest.raises(
        witness.FoundationWitnessError,
        match="foundation-roster-head-witness-ahead",
    ):
        witness.ensure_foundation_roster_head_witness(
            DB(),
            HEAD,
            get_impl=lambda *_args, **_kwargs: Response(ahead),
        )


def test_roster_head_witness_rejects_same_sequence_fork():
    fork = receipt(headSha256="1" * 64)

    with pytest.raises(
        witness.FoundationWitnessError,
        match="foundation-roster-head-witness-fork",
    ):
        witness.ensure_foundation_roster_head_witness(
            DB(),
            HEAD,
            get_impl=lambda *_args, **_kwargs: Response(fork),
        )


def test_roster_head_witness_rejects_unexpected_identity_or_type():
    bad = receipt(witnessId="other-witness")

    with pytest.raises(
        witness.FoundationWitnessError,
        match="foundation-roster-head-witness-response-invalid",
    ):
        witness.ensure_foundation_roster_head_witness(
            DB(),
            HEAD,
            get_impl=lambda *_args, **_kwargs: Response(bad),
        )
