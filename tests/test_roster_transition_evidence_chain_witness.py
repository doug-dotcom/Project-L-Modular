import json

import pytest

from services import roster_transition_evidence_chain_witness as witness


class FakeRedis:
    def __init__(self):
        self.rows = {}

    def hgetall(self, key):
        return dict(self.rows.get(key, {}))

    def eval(self, _script, _numkeys, key, *args):
        (
            generation,
            rows,
            previous_chain_tag,
            evidence_sha,
            chain_tag,
            checkpoint_json,
        ) = args
        generation = int(generation)
        rows = int(rows)
        current = self.rows.get(key)

        if current is None:
            if (
                generation != 1
                or rows != 0
                or previous_chain_tag
                or evidence_sha
                or chain_tag
            ):
                return ["bootstrap-invalid"]
            self.rows[key] = {
                "generation": "1",
                "rows": "0",
                "previous_chain_tag": "",
                "evidence_sha256": "",
                "chain_tag": "",
                "checkpoint_json": checkpoint_json,
            }
            return ["created"]

        current_generation = int(current["generation"])
        current_rows = int(current["rows"])
        if generation < current_generation:
            return ["rollback"]
        if generation == current_generation:
            if (
                rows != current_rows
                or previous_chain_tag
                    != current["previous_chain_tag"]
                or evidence_sha != current["evidence_sha256"]
                or chain_tag != current["chain_tag"]
            ):
                return ["fork"]
            current["checkpoint_json"] = checkpoint_json
            return ["existing"]

        if generation != current_generation + 1:
            return ["generation-gap"]
        if rows != current_rows + 1:
            return ["row-gap"]
        if previous_chain_tag != current["chain_tag"]:
            if not (
                current_generation == 1
                and current["chain_tag"] == ""
                and previous_chain_tag == "0" * 64
            ):
                return ["predecessor-chain-mismatch"]
        if not evidence_sha or not chain_tag:
            return ["advanced-head-missing"]

        self.rows[key] = {
            "generation": str(generation),
            "rows": str(rows),
            "previous_chain_tag": previous_chain_tag,
            "evidence_sha256": evidence_sha,
            "chain_tag": chain_tag,
            "checkpoint_json": checkpoint_json,
        }
        return ["advanced"]


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv(
        witness.KEYRING_ENV,
        json.dumps({
            "chain-a": "S" * 48,
            "chain-b": "T" * 48,
        }),
    )
    monkeypatch.setenv(witness.ACTIVE_KEY_ENV, "chain-a")


def genesis():
    return {
        "status": "empty",
        "chainVersion": 1,
        "latestGeneration": 1,
        "rows": 0,
    }


def generation_two(chain_tag="a" * 64, evidence_sha="b" * 64):
    return {
        "status": "verified",
        "chainVersion": 1,
        "latestGeneration": 2,
        "rows": 1,
        "latestPreviousChainTag": "0" * 64,
        "latestEvidenceSha256": evidence_sha,
        "latestChainTag": chain_tag,
    }


def generation_three(
    previous_chain_tag="a" * 64,
    chain_tag="c" * 64,
    evidence_sha="d" * 64,
):
    return {
        "status": "verified",
        "chainVersion": 1,
        "latestGeneration": 3,
        "rows": 2,
        "latestPreviousChainTag": previous_chain_tag,
        "latestEvidenceSha256": evidence_sha,
        "latestChainTag": chain_tag,
    }


def test_genesis_witness_bootstraps_and_is_idempotent():
    redis = FakeRedis()

    first = witness.ensure_chain_witness(
        genesis(),
        redis_client=redis,
    )
    second = witness.ensure_chain_witness(
        genesis(),
        redis_client=redis,
    )

    assert first["status"] == "verified"
    assert first["mode"] == "created"
    assert first["generation"] == 1
    assert first["rows"] == 0
    assert first["chain_tag"] is None
    assert second["mode"] == "existing"
    assert second["storage"] == "railway-redis-volume"


def test_generation_two_must_extend_zero_genesis_head():
    redis = FakeRedis()
    witness.ensure_chain_witness(genesis(), redis_client=redis)

    result = witness.ensure_chain_witness(
        generation_two(),
        redis_client=redis,
    )

    assert result["mode"] == "advanced"
    assert result["generation"] == 2
    assert result["chain_tag"] == "a" * 64
    assert result["evidence_sha256"] == "b" * 64


def test_generation_three_must_extend_exact_previous_chain_tag():
    redis = FakeRedis()
    witness.ensure_chain_witness(genesis(), redis_client=redis)
    witness.ensure_chain_witness(
        generation_two(),
        redis_client=redis,
    )

    bad_redis = FakeRedis()
    witness.ensure_chain_witness(
        genesis(),
        redis_client=bad_redis,
    )
    witness.ensure_chain_witness(
        generation_two(),
        redis_client=bad_redis,
    )
    bad = generation_three(
        previous_chain_tag="f" * 64,
        chain_tag="e" * 64,
        evidence_sha="9" * 64,
    )
    with pytest.raises(
        witness.RosterEvidenceChainWitnessError,
        match="predecessor-chain-mismatch",
    ):
        witness.ensure_chain_witness(
            bad,
            redis_client=bad_redis,
        )

    result = witness.ensure_chain_witness(
        generation_three(),
        redis_client=redis,
    )
    assert result["mode"] == "advanced"


def test_same_generation_history_rewrite_is_rejected():
    redis = FakeRedis()
    witness.ensure_chain_witness(genesis(), redis_client=redis)
    witness.ensure_chain_witness(
        generation_two(),
        redis_client=redis,
    )

    rewritten = generation_two(
        chain_tag="f" * 64,
        evidence_sha="b" * 64,
    )
    with pytest.raises(
        witness.RosterEvidenceChainWitnessError,
        match="witness-fork",
    ):
        witness.ensure_chain_witness(
            rewritten,
            redis_client=redis,
        )


def test_older_chain_is_rejected_after_high_water_advances():
    redis = FakeRedis()
    witness.ensure_chain_witness(genesis(), redis_client=redis)
    witness.ensure_chain_witness(
        generation_two(),
        redis_client=redis,
    )

    with pytest.raises(
        witness.RosterEvidenceChainWitnessError,
        match="witness-ahead",
    ):
        witness.ensure_chain_witness(
            genesis(),
            redis_client=redis,
        )


def test_checkpoint_hmac_tampering_fails_closed():
    redis = FakeRedis()
    witness.ensure_chain_witness(genesis(), redis_client=redis)
    row = redis.rows[witness.REDIS_KEY]
    checkpoint = json.loads(row["checkpoint_json"])
    checkpoint["authTag"] = "0" * 64
    row["checkpoint_json"] = json.dumps(
        checkpoint,
        separators=(",", ":"),
        sort_keys=True,
    )

    with pytest.raises(
        witness.RosterEvidenceChainWitnessError,
        match="witness-auth-failed",
    ):
        witness.read_chain_witness(redis_client=redis)


def test_retired_witness_key_rejects_old_checkpoint(monkeypatch):
    redis = FakeRedis()
    witness.ensure_chain_witness(genesis(), redis_client=redis)

    monkeypatch.setenv(
        witness.KEYRING_ENV,
        json.dumps({"chain-b": "T" * 48}),
    )
    monkeypatch.setenv(witness.ACTIVE_KEY_ENV, "chain-b")

    with pytest.raises(
        witness.RosterEvidenceChainWitnessError,
        match="witness-key-retired",
    ):
        witness.read_chain_witness(redis_client=redis)
