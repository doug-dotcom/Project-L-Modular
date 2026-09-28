import json

import pytest

from services import foundation_chain_redis_checkpoint as mirror


ZERO = "0" * 64
TAG1 = "1" * 64
TAG2 = "2" * 64


class FakeRedis:
    def __init__(self):
        self.row = {}

    def hgetall(self, key):
        if key != mirror.REDIS_KEY:
            return {}
        return dict(self.row)

    def eval(self, _script, _numkeys, key, *args):
        assert key == mirror.REDIS_KEY
        sequence, previous, chain_tag, checkpoint_json = args
        sequence = int(sequence)

        if not self.row:
            if sequence != 1 or previous != ZERO:
                return ["genesis-invalid"]
            self.row = {
                "sequence": str(sequence),
                "previous_chain_tag": previous,
                "chain_tag": chain_tag,
                "checkpoint_json": checkpoint_json,
            }
            return ["created"]

        current_sequence = int(self.row["sequence"])
        current_previous = self.row["previous_chain_tag"]
        current_chain = self.row["chain_tag"]
        if sequence < current_sequence:
            return ["rollback"]
        if sequence == current_sequence:
            if previous == current_previous and chain_tag == current_chain:
                return ["existing"]
            return ["equivocation"]
        if sequence != current_sequence + 1:
            return ["sequence-gap"]
        if previous != current_chain:
            return ["predecessor-mismatch"]

        self.row = {
            "sequence": str(sequence),
            "previous_chain_tag": previous,
            "chain_tag": chain_tag,
            "checkpoint_json": checkpoint_json,
        }
        return ["advanced"]


@pytest.fixture(autouse=True)
def keyring(monkeypatch):
    monkeypatch.setenv(
        mirror.KEYRING_ENV,
        json.dumps({
            "foundation-chain-redis-a": "R" * 48,
            "foundation-chain-redis-b": "S" * 48,
        }),
    )
    monkeypatch.setenv(
        mirror.ACTIVE_KEY_ENV,
        "foundation-chain-redis-a",
    )


def chain(sequence, previous, tag):
    return {
        "status": "verified",
        "witness_id": "foundation-project-l",
        "chain_version": 1,
        "sequence": sequence,
        "previous_chain_tag": previous,
        "chain_tag": tag,
    }


def test_redis_checkpoint_hmac_detects_tampering():
    receipt = mirror.create_redis_foundation_chain_checkpoint(
        chain(1, ZERO, TAG1),
    )
    assert mirror.verify_redis_foundation_chain_checkpoint(
        receipt
    )["chainTag"] == TAG1

    receipt["chainTag"] = "f" * 64
    with pytest.raises(
        mirror.RedisFoundationChainCheckpointError,
        match="foundation-chain-redis-auth-failed",
    ):
        mirror.verify_redis_foundation_chain_checkpoint(receipt)


def test_redis_checkpoint_bootstraps_and_is_idempotent():
    redis = FakeRedis()

    first = mirror.ensure_redis_foundation_chain_checkpoint(
        chain(1, ZERO, TAG1),
        redis_client=redis,
    )
    second = mirror.ensure_redis_foundation_chain_checkpoint(
        chain(1, ZERO, TAG1),
        redis_client=redis,
    )

    assert first["mode"] == "created"
    assert second["mode"] == "existing"
    assert second["storage"] == "railway-redis-volume"


def test_redis_checkpoint_advances_one_chain_link():
    redis = FakeRedis()
    mirror.ensure_redis_foundation_chain_checkpoint(
        chain(1, ZERO, TAG1),
        redis_client=redis,
    )

    result = mirror.ensure_redis_foundation_chain_checkpoint(
        chain(2, TAG1, TAG2),
        redis_client=redis,
    )

    assert result["mode"] == "advanced"
    assert result["sequence"] == 2
    assert result["previous_chain_tag"] == TAG1
    assert result["chain_tag"] == TAG2


def test_redis_checkpoint_ahead_detects_foundation_rollback():
    redis = FakeRedis()
    mirror.ensure_redis_foundation_chain_checkpoint(
        chain(1, ZERO, TAG1),
        redis_client=redis,
    )
    mirror.ensure_redis_foundation_chain_checkpoint(
        chain(2, TAG1, TAG2),
        redis_client=redis,
    )

    with pytest.raises(
        mirror.RedisFoundationChainCheckpointError,
        match="foundation-chain-redis-ahead",
    ):
        mirror.ensure_redis_foundation_chain_checkpoint(
            chain(1, ZERO, TAG1),
            redis_client=redis,
        )


def test_redis_checkpoint_same_sequence_fork_fails_closed():
    redis = FakeRedis()
    mirror.ensure_redis_foundation_chain_checkpoint(
        chain(1, ZERO, TAG1),
        redis_client=redis,
    )

    with pytest.raises(
        mirror.RedisFoundationChainCheckpointError,
        match="foundation-chain-redis-fork",
    ):
        mirror.ensure_redis_foundation_chain_checkpoint(
            chain(1, ZERO, "f" * 64),
            redis_client=redis,
        )


def test_redis_checkpoint_gap_and_bad_predecessor_fail_closed():
    redis = FakeRedis()
    mirror.ensure_redis_foundation_chain_checkpoint(
        chain(1, ZERO, TAG1),
        redis_client=redis,
    )

    with pytest.raises(
        mirror.RedisFoundationChainCheckpointError,
        match="foundation-chain-redis-sequence-gap",
    ):
        mirror.ensure_redis_foundation_chain_checkpoint(
            chain(3, TAG2, "3" * 64),
            redis_client=redis,
        )

    with pytest.raises(
        mirror.RedisFoundationChainCheckpointError,
        match="foundation-chain-redis-predecessor-mismatch",
    ):
        mirror.ensure_redis_foundation_chain_checkpoint(
            chain(2, "f" * 64, TAG2),
            redis_client=redis,
        )


def test_redis_storage_fields_are_cross_checked():
    redis = FakeRedis()
    mirror.ensure_redis_foundation_chain_checkpoint(
        chain(1, ZERO, TAG1),
        redis_client=redis,
    )
    redis.row["chain_tag"] = "f" * 64

    with pytest.raises(
        mirror.RedisFoundationChainCheckpointError,
        match="foundation-chain-redis-storage-mismatch",
    ):
        mirror.read_redis_foundation_chain_checkpoint(
            redis_client=redis,
        )
