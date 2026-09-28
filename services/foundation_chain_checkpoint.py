"""Durable Project-L checkpoint for the accepted Foundation witness chain."""

from __future__ import annotations

import re
from typing import Any


SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
WITNESS_ID = "foundation-project-l"
CHECKPOINT_TYPE = "foundation_witness_chain_high_water"
CHECKPOINT_STORAGE = "project-l-supabase-vault-hmac"


class FoundationChainCheckpointError(RuntimeError):
    pass


def _project_chain(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FoundationChainCheckpointError(
            "foundation-chain-checkpoint-chain-invalid"
        )

    sequence = value.get("sequence")
    previous_chain_tag = value.get("previous_chain_tag")
    chain_tag = value.get("chain_tag")
    if (
        value.get("status") != "verified"
        or value.get("witness_id") != WITNESS_ID
        or value.get("chain_version") != 1
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or sequence < 1
        or sequence > 10_000_000
        or not isinstance(previous_chain_tag, str)
        or SHA256_RE.fullmatch(previous_chain_tag) is None
        or not isinstance(chain_tag, str)
        or SHA256_RE.fullmatch(chain_tag) is None
        or (
            sequence == 1
            and previous_chain_tag != "0" * 64
        )
    ):
        raise FoundationChainCheckpointError(
            "foundation-chain-checkpoint-chain-invalid"
        )

    return {
        "witness_id": WITNESS_ID,
        "chain_version": 1,
        "sequence": sequence,
        "previous_chain_tag": previous_chain_tag,
        "chain_tag": chain_tag,
    }


def _project_checkpoint(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FoundationChainCheckpointError(
            "foundation-chain-checkpoint-response-invalid"
        )

    sequence = value.get("sequence")
    previous_chain_tag = value.get("previousChainTag")
    chain_tag = value.get("chainTag")
    auth_key_id = value.get("authKeyId")
    ledger_rows = value.get("ledgerRows")
    if (
        value.get("checkpointVersion") != 1
        or value.get("checkpointType") != CHECKPOINT_TYPE
        or value.get("witnessId") != WITNESS_ID
        or value.get("chainVersion") != 1
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or sequence < 1
        or sequence > 10_000_000
        or not isinstance(previous_chain_tag, str)
        or SHA256_RE.fullmatch(previous_chain_tag) is None
        or not isinstance(chain_tag, str)
        or SHA256_RE.fullmatch(chain_tag) is None
        or not isinstance(auth_key_id, str)
        or not auth_key_id
        or value.get("storage") != CHECKPOINT_STORAGE
        or (
            ledger_rows is not None
            and (
                not isinstance(ledger_rows, int)
                or isinstance(ledger_rows, bool)
                or ledger_rows < 1
            )
        )
    ):
        raise FoundationChainCheckpointError(
            "foundation-chain-checkpoint-response-invalid"
        )

    if sequence == 1 and previous_chain_tag != "0" * 64:
        raise FoundationChainCheckpointError(
            "foundation-chain-checkpoint-response-invalid"
        )

    return {
        "checkpoint_version": 1,
        "witness_id": WITNESS_ID,
        "chain_version": 1,
        "sequence": sequence,
        "previous_chain_tag": previous_chain_tag,
        "chain_tag": chain_tag,
        "auth_key_id": auth_key_id,
        "storage": CHECKPOINT_STORAGE,
        "ledger_rows": ledger_rows,
    }


def _snapshot(db) -> tuple[str, dict | None, str | None]:
    try:
        result = db.rpc(
            "shine_ai_foundation_chain_checkpoint_snapshot_v1",
            {},
        ).execute()
    except Exception as exc:
        raise FoundationChainCheckpointError(
            "foundation-chain-checkpoint-snapshot-unavailable"
        ) from exc

    payload = result.data if isinstance(result.data, dict) else {}
    status = str(payload.get("status") or "")
    if status == "unbootstrapped":
        return status, None, None
    if status != "trusted":
        return (
            status or "unavailable",
            None,
            str(
                payload.get("reason_code")
                or "foundation-chain-checkpoint-storage-invalid"
            ),
        )
    return status, _project_checkpoint(payload.get("checkpoint")), None


def _observe(db, chain: dict[str, Any]) -> dict[str, Any]:
    try:
        result = db.rpc(
            "shine_ai_foundation_chain_checkpoint_observe_v1",
            {
                "p_witness_id": chain["witness_id"],
                "p_chain_version": chain["chain_version"],
                "p_sequence": chain["sequence"],
                "p_previous_chain_tag": chain["previous_chain_tag"],
                "p_chain_tag": chain["chain_tag"],
            },
        ).execute()
    except Exception as exc:
        raise FoundationChainCheckpointError(
            "foundation-chain-checkpoint-observe-unavailable"
        ) from exc

    payload = result.data if isinstance(result.data, dict) else {}
    if payload.get("status") != "trusted":
        raise FoundationChainCheckpointError(
            str(
                payload.get("reason_code")
                or "foundation-chain-checkpoint-observe-rejected"
            )
        )
    return {
        **_project_checkpoint(payload.get("checkpoint")),
        "mode": str(payload.get("mode") or ""),
    }


def _matches_chain(checkpoint: dict[str, Any], chain: dict[str, Any]) -> bool:
    return (
        checkpoint["witness_id"] == chain["witness_id"]
        and checkpoint["chain_version"] == chain["chain_version"]
        and checkpoint["sequence"] == chain["sequence"]
        and checkpoint["previous_chain_tag"] == chain["previous_chain_tag"]
        and checkpoint["chain_tag"] == chain["chain_tag"]
    )


def ensure_foundation_chain_checkpoint(
    db,
    chain_receipt: Any,
) -> dict[str, Any]:
    chain = _project_chain(chain_receipt)
    status, current, reason = _snapshot(db)

    if status == "unbootstrapped":
        if chain["sequence"] != 1:
            raise FoundationChainCheckpointError(
                "foundation-chain-checkpoint-history-missing"
            )
        observed = _observe(db, chain)
        mode = "genesis"
    elif status == "trusted" and current is not None:
        if current["sequence"] > chain["sequence"]:
            raise FoundationChainCheckpointError(
                "foundation-chain-checkpoint-ahead"
            )
        if current["sequence"] == chain["sequence"]:
            if not _matches_chain(current, chain):
                raise FoundationChainCheckpointError(
                    "foundation-chain-checkpoint-fork"
                )
            return {
                "status": "verified",
                **current,
                "mode": "existing",
            }
        if chain["sequence"] != current["sequence"] + 1:
            raise FoundationChainCheckpointError(
                "foundation-chain-checkpoint-sequence-gap"
            )
        if chain["previous_chain_tag"] != current["chain_tag"]:
            raise FoundationChainCheckpointError(
                "foundation-chain-checkpoint-predecessor-mismatch"
            )
        observed = _observe(db, chain)
        mode = "advanced"
    else:
        raise FoundationChainCheckpointError(
            reason or "foundation-chain-checkpoint-storage-invalid"
        )

    if not _matches_chain(observed, chain):
        raise FoundationChainCheckpointError(
            "foundation-chain-checkpoint-commit-mismatch"
        )

    final_status, final, final_reason = _snapshot(db)
    if (
        final_status != "trusted"
        or final is None
        or not _matches_chain(final, chain)
    ):
        raise FoundationChainCheckpointError(
            final_reason or "foundation-chain-checkpoint-write-unverified"
        )

    return {
        "status": "verified",
        **final,
        "mode": mode,
    }


__all__ = [
    "CHECKPOINT_STORAGE",
    "CHECKPOINT_TYPE",
    "FoundationChainCheckpointError",
    "WITNESS_ID",
    "ensure_foundation_chain_checkpoint",
]
