import pytest

from services import foundation_chain_checkpoint as checkpoint


ZERO = "0" * 64
TAG1 = "1" * 64
TAG2 = "2" * 64


class Result:
    def __init__(self, data):
        self.data = data


class FakeDB:
    def __init__(self):
        self.state = None
        self.ledger = []

    def _checkpoint(self):
        if self.state is None:
            return None
        return {
            "checkpointVersion": 1,
            "checkpointType": "foundation_witness_chain_high_water",
            "witnessId": "foundation-project-l",
            "chainVersion": 1,
            "sequence": self.state["sequence"],
            "previousChainTag": self.state["previous_chain_tag"],
            "chainTag": self.state["chain_tag"],
            "authKeyId": "project-l-foundation-chain-checkpoint-v1",
            "storage": "project-l-supabase-vault-hmac",
            "ledgerRows": len(self.ledger),
        }

    def rpc(self, name, params):
        db = self

        class Call:
            def execute(self):
                if name == "shine_ai_foundation_chain_checkpoint_snapshot_v1":
                    if db.state is None:
                        return Result({"status": "unbootstrapped"})
                    return Result({
                        "status": "trusted",
                        "checkpoint": db._checkpoint(),
                    })

                if name == "shine_ai_foundation_chain_checkpoint_observe_v1":
                    sequence = params["p_sequence"]
                    previous = params["p_previous_chain_tag"]
                    tag = params["p_chain_tag"]
                    if db.state is None:
                        if sequence != 1 or previous != ZERO:
                            return Result({
                                "status": "rejected",
                                "reason_code":
                                    "foundation-chain-checkpoint-genesis-invalid",
                            })
                        mode = "genesis"
                    else:
                        current = db.state
                        if sequence < current["sequence"]:
                            return Result({
                                "status": "rejected",
                                "reason_code":
                                    "foundation-chain-checkpoint-rollback",
                            })
                        if sequence == current["sequence"]:
                            if (
                                previous == current["previous_chain_tag"]
                                and tag == current["chain_tag"]
                            ):
                                return Result({
                                    "status": "trusted",
                                    "mode": "existing",
                                    "checkpoint": db._checkpoint(),
                                })
                            return Result({
                                "status": "rejected",
                                "reason_code":
                                    "foundation-chain-checkpoint-equivocation",
                            })
                        if sequence != current["sequence"] + 1:
                            return Result({
                                "status": "rejected",
                                "reason_code":
                                    "foundation-chain-checkpoint-sequence-gap",
                            })
                        if previous != current["chain_tag"]:
                            return Result({
                                "status": "rejected",
                                "reason_code":
                                    "foundation-chain-checkpoint-predecessor-mismatch",
                            })
                        mode = "advanced"

                    db.state = {
                        "sequence": sequence,
                        "previous_chain_tag": previous,
                        "chain_tag": tag,
                    }
                    db.ledger.append(dict(db.state))
                    return Result({
                        "status": "trusted",
                        "mode": mode,
                        "checkpoint": db._checkpoint(),
                    })

                raise AssertionError(name)

        return Call()


def chain(sequence, previous, tag):
    return {
        "status": "verified",
        "witness_id": "foundation-project-l",
        "chain_version": 1,
        "sequence": sequence,
        "previous_chain_tag": previous,
        "chain_tag": tag,
    }


def test_checkpoint_bootstraps_exact_foundation_genesis():
    db = FakeDB()

    result = checkpoint.ensure_foundation_chain_checkpoint(
        db,
        chain(1, ZERO, TAG1),
    )

    assert result["status"] == "verified"
    assert result["mode"] == "genesis"
    assert result["sequence"] == 1
    assert result["chain_tag"] == TAG1
    assert result["ledger_rows"] == 1


def test_checkpoint_is_idempotent_for_same_chain_head():
    db = FakeDB()
    checkpoint.ensure_foundation_chain_checkpoint(
        db,
        chain(1, ZERO, TAG1),
    )

    result = checkpoint.ensure_foundation_chain_checkpoint(
        db,
        chain(1, ZERO, TAG1),
    )

    assert result["mode"] == "existing"
    assert len(db.ledger) == 1


def test_checkpoint_advances_exactly_one_link():
    db = FakeDB()
    checkpoint.ensure_foundation_chain_checkpoint(
        db,
        chain(1, ZERO, TAG1),
    )

    result = checkpoint.ensure_foundation_chain_checkpoint(
        db,
        chain(2, TAG1, TAG2),
    )

    assert result["mode"] == "advanced"
    assert result["sequence"] == 2
    assert result["previous_chain_tag"] == TAG1
    assert result["chain_tag"] == TAG2
    assert result["ledger_rows"] == 2


def test_checkpoint_ahead_detects_foundation_rollback():
    db = FakeDB()
    checkpoint.ensure_foundation_chain_checkpoint(
        db,
        chain(1, ZERO, TAG1),
    )
    checkpoint.ensure_foundation_chain_checkpoint(
        db,
        chain(2, TAG1, TAG2),
    )

    with pytest.raises(
        checkpoint.FoundationChainCheckpointError,
        match="foundation-chain-checkpoint-ahead",
    ):
        checkpoint.ensure_foundation_chain_checkpoint(
            db,
            chain(1, ZERO, TAG1),
        )


def test_same_sequence_fork_fails_closed():
    db = FakeDB()
    checkpoint.ensure_foundation_chain_checkpoint(
        db,
        chain(1, ZERO, TAG1),
    )

    with pytest.raises(
        checkpoint.FoundationChainCheckpointError,
        match="foundation-chain-checkpoint-fork",
    ):
        checkpoint.ensure_foundation_chain_checkpoint(
            db,
            chain(1, ZERO, "f" * 64),
        )


def test_sequence_gap_fails_closed_before_observe():
    db = FakeDB()
    checkpoint.ensure_foundation_chain_checkpoint(
        db,
        chain(1, ZERO, TAG1),
    )

    with pytest.raises(
        checkpoint.FoundationChainCheckpointError,
        match="foundation-chain-checkpoint-sequence-gap",
    ):
        checkpoint.ensure_foundation_chain_checkpoint(
            db,
            chain(3, TAG2, "3" * 64),
        )


def test_wrong_predecessor_fails_closed():
    db = FakeDB()
    checkpoint.ensure_foundation_chain_checkpoint(
        db,
        chain(1, ZERO, TAG1),
    )

    with pytest.raises(
        checkpoint.FoundationChainCheckpointError,
        match="foundation-chain-checkpoint-predecessor-mismatch",
    ):
        checkpoint.ensure_foundation_chain_checkpoint(
            db,
            chain(2, "f" * 64, TAG2),
        )


def test_non_genesis_cannot_bootstrap_missing_checkpoint():
    db = FakeDB()

    with pytest.raises(
        checkpoint.FoundationChainCheckpointError,
        match="foundation-chain-checkpoint-history-missing",
    ):
        checkpoint.ensure_foundation_chain_checkpoint(
            db,
            chain(2, TAG1, TAG2),
        )
