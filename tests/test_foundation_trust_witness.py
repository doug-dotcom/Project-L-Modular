import json

import pytest

from services import foundation_trust_witness as witness


class Result:
    def __init__(self, data):
        self.data = data


class FakeDB:
    def rpc(self, name, params):
        assert name == "concierge_foundation_client_token_v1"
        assert params == {}

        class Call:
            def execute(self):
                return Result("C" * 48)

        return Call()


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {"content-length": str(len(self.content))}

    def json(self):
        return self._payload


def head(sequence=1, generation=1, suffix="a"):
    return {
        "headVersion": 1,
        "headType": "decision_trace_trust_state_monotonic_head",
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": "storage-a",
        "checkpointChainVersion": 1,
        "sequence": sequence,
        "checkpointSha256": "1" * 64,
        "generation": generation,
        "keyset_sha256": suffix * 64,
        "stateSha256": ("b" if suffix == "a" else "c") * 64,
        "headSha256": ("d" if sequence == 1 else "e") * 64,
        "authTag": "f" * 64,
    }


def witness_payload(local_head, *, replayed=False):
    return {
        "status": "witnessed",
        "replayed": replayed,
        "witnessVersion": 1,
        "witnessType": (
            "decision_trace_trust_state_monotonic_head_witness"
        ),
        "authAlgorithm": "HMAC-SHA-256",
        "witnessId": "foundation-project-l",
        "authKeyId": "foundation-witness-v1",
        "headVersion": 1,
        "sequence": local_head["sequence"],
        "headSha256": local_head["headSha256"],
        "generation": local_head["generation"],
        "keyset_sha256": local_head["keyset_sha256"],
        "stateSha256": local_head["stateSha256"],
        "authTag": "9" * 64,
    }


def test_empty_foundation_witness_records_local_genesis(monkeypatch):
    local_head = head()
    monkeypatch.setattr(
        witness,
        "prepare_monotonic_head",
        lambda *args, **kwargs: {
            "status": "ready",
            "mode": "created",
            "head": local_head,
        },
    )
    post_calls = []

    def fake_get(*args, **kwargs):
        return FakeResponse({
            "status": "empty",
            "witnessId": "foundation-project-l",
        })

    def fake_post(url, **kwargs):
        post_calls.append((url, kwargs))
        assert kwargs["headers"]["X-Shine-Client-Token"] == "C" * 48
        assert kwargs["json"]["sequence"] == 1
        return FakeResponse(witness_payload(local_head))

    result = witness.ensure_foundation_trust_witness(
        FakeDB(),
        {},
        get_impl=fake_get,
        post_impl=fake_post,
    )

    assert result["status"] == "verified"
    assert result["mode"] == "created"
    assert result["sequence"] == 1
    assert result["independent_retention"] == "foundation-supabase"
    assert "authTag" not in result
    assert len(post_calls) == 1


def test_existing_external_witness_is_idempotent(monkeypatch):
    local_head = head()
    monkeypatch.setattr(
        witness,
        "prepare_monotonic_head",
        lambda *args, **kwargs: {
            "status": "ready",
            "mode": "existing-head",
            "head": local_head,
        },
    )

    result = witness.ensure_foundation_trust_witness(
        FakeDB(),
        {},
        get_impl=lambda *args, **kwargs: FakeResponse(
            witness_payload(local_head, replayed=True)
        ),
        post_impl=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("existing witness must not be rewritten")
        ),
    )

    assert result["status"] == "verified"
    assert result["mode"] == "existing-witness"
    assert result["head_sha256"] == local_head["headSha256"]


def test_external_witness_advances_exactly_one_sequence(monkeypatch):
    previous = head(sequence=1, generation=1, suffix="a")
    current = head(sequence=2, generation=2, suffix="c")
    monkeypatch.setattr(
        witness,
        "prepare_monotonic_head",
        lambda *args, **kwargs: {
            "status": "ready",
            "mode": "advanced",
            "head": current,
        },
    )

    result = witness.ensure_foundation_trust_witness(
        FakeDB(),
        {},
        get_impl=lambda *args, **kwargs: FakeResponse(
            witness_payload(previous)
        ),
        post_impl=lambda *args, **kwargs: FakeResponse(
            witness_payload(current)
        ),
    )

    assert result["status"] == "verified"
    assert result["mode"] == "advanced"
    assert result["sequence"] == 2
    assert result["generation"] == 2


def test_external_witness_ahead_is_rollback_evidence(monkeypatch):
    local = head(sequence=1, generation=1, suffix="a")
    ahead = head(sequence=2, generation=2, suffix="c")
    monkeypatch.setattr(
        witness,
        "prepare_monotonic_head",
        lambda *args, **kwargs: {
            "status": "ready",
            "mode": "existing-head",
            "head": local,
        },
    )

    with pytest.raises(
        witness.FoundationWitnessError,
        match="foundation-witness-ahead",
    ):
        witness.ensure_foundation_trust_witness(
            FakeDB(),
            {},
            get_impl=lambda *args, **kwargs: FakeResponse(
                witness_payload(ahead)
            ),
        )


def test_same_sequence_external_fork_fails_closed(monkeypatch):
    local = head(sequence=2, generation=2, suffix="c")
    fork = dict(local)
    fork["headSha256"] = "7" * 64
    monkeypatch.setattr(
        witness,
        "prepare_monotonic_head",
        lambda *args, **kwargs: {
            "status": "ready",
            "mode": "existing-head",
            "head": local,
        },
    )

    with pytest.raises(
        witness.FoundationWitnessError,
        match="foundation-witness-fork",
    ):
        witness.ensure_foundation_trust_witness(
            FakeDB(),
            {},
            get_impl=lambda *args, **kwargs: FakeResponse(
                witness_payload(fork)
            ),
        )


def test_external_sequence_gap_fails_before_post(monkeypatch):
    local = head(sequence=4, generation=2, suffix="c")
    previous = head(sequence=1, generation=1, suffix="a")
    monkeypatch.setattr(
        witness,
        "prepare_monotonic_head",
        lambda *args, **kwargs: {
            "status": "ready",
            "mode": "advanced",
            "head": local,
        },
    )

    with pytest.raises(
        witness.FoundationWitnessError,
        match="foundation-witness-sequence-gap",
    ):
        witness.ensure_foundation_trust_witness(
            FakeDB(),
            {},
            get_impl=lambda *args, **kwargs: FakeResponse(
                witness_payload(previous)
            ),
            post_impl=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("gap must fail before network write")
            ),
        )
