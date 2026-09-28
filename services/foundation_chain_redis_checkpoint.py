"""Independent Railway Redis mirror of Project L's Foundation-chain checkpoint."""

from __future__ import annotations

import hmac
import hashlib
import json
import os
import re
from typing import Any

from redis.exceptions import RedisError

from services.shine_trust_storage import (
    TrustStorageError,
    _redis_client,
)


SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
KEY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
WITNESS_ID = "foundation-project-l"
CHECKPOINT_TYPE = "foundation_witness_chain_high_water"
CHECKPOINT_STORAGE = "railway-redis-volume"
REDIS_KEY = "shine:project-l:foundation-chain-checkpoint:redis:v1"
AUTH_DOMAIN = "shine:project-l:foundation-chain-checkpoint:redis:v1"
KEYRING_ENV = "SHINE_TRACE_FOUNDATION_CHAIN_CHECKPOINT_REDIS_KEYRING_JSON"
ACTIVE_KEY_ENV = "SHINE_TRACE_FOUNDATION_CHAIN_CHECKPOINT_REDIS_ACTIVE_KEY_ID"

_CAS = r"""
local key = KEYS[1]
local next_sequence = tonumber(ARGV[1])
local next_previous = ARGV[2]
local next_chain = ARGV[3]
local checkpoint_json = ARGV[4]

local current_sequence_raw = redis.call('HGET', key, 'sequence')
if not current_sequence_raw then
  if next_sequence ~= 1 or next_previous ~= string.rep('0',64) then
    return {'genesis-invalid'}
  end
  redis.call(
    'HSET',
    key,
    'sequence', tostring(next_sequence),
    'previous_chain_tag', next_previous,
    'chain_tag', next_chain,
    'checkpoint_json', checkpoint_json
  )
  return {'created'}
end

local current_sequence = tonumber(current_sequence_raw)
local current_previous = redis.call('HGET', key, 'previous_chain_tag') or ''
local current_chain = redis.call('HGET', key, 'chain_tag') or ''

if next_sequence < current_sequence then
  return {'rollback'}
end

if next_sequence == current_sequence then
  if next_previous == current_previous and next_chain == current_chain then
    return {'existing'}
  end
  return {'equivocation'}
end

if next_sequence ~= current_sequence + 1 then
  return {'sequence-gap'}
end

if next_previous ~= current_chain then
  return {'predecessor-mismatch'}
end

redis.call(
  'HSET',
  key,
  'sequence', tostring(next_sequence),
  'previous_chain_tag', next_previous,
  'chain_tag', next_chain,
  'checkpoint_json', checkpoint_json
)
return {'advanced'}
"""


class RedisFoundationChainCheckpointError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _hmac_sha256(secret: str, value: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _keyring() -> tuple[str, dict[str, str]]:
    raw = os.getenv(KEYRING_ENV, "").strip()
    active = os.getenv(ACTIVE_KEY_ENV, "").strip()
    if not raw or KEY_ID_RE.fullmatch(active) is None:
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-keyring-unavailable"
        )
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-keyring-invalid"
        ) from exc
    if not isinstance(parsed, dict) or not 1 <= len(parsed) <= 4:
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-keyring-invalid"
        )

    keyring: dict[str, str] = {}
    for raw_key, raw_secret in parsed.items():
        key_id = str(raw_key)
        if (
            KEY_ID_RE.fullmatch(key_id) is None
            or not isinstance(raw_secret, str)
            or len(raw_secret) < 32
            or len(raw_secret) > 8192
        ):
            raise RedisFoundationChainCheckpointError(
                "foundation-chain-redis-keyring-invalid"
            )
        keyring[key_id] = raw_secret

    if active not in keyring:
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-active-key-unavailable"
        )
    return active, keyring


def _secret_for(key_id: str) -> str:
    _active, keyring = _keyring()
    secret = keyring.get(key_id)
    if secret is None:
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-auth-key-retired"
        )
    return secret


def _project_chain(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-chain-invalid"
        )
    sequence = value.get("sequence")
    previous = value.get("previous_chain_tag")
    chain_tag = value.get("chain_tag")
    if (
        value.get("status") != "verified"
        or value.get("witness_id") != WITNESS_ID
        or value.get("chain_version") != 1
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or not 1 <= sequence <= 10_000_000
        or not isinstance(previous, str)
        or SHA256_RE.fullmatch(previous) is None
        or not isinstance(chain_tag, str)
        or SHA256_RE.fullmatch(chain_tag) is None
        or (sequence == 1 and previous != "0" * 64)
    ):
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-chain-invalid"
        )
    return {
        "status": "verified",
        "witness_id": WITNESS_ID,
        "chain_version": 1,
        "sequence": sequence,
        "previous_chain_tag": previous,
        "chain_tag": chain_tag,
    }


def create_redis_foundation_chain_checkpoint(
    chain_receipt: Any,
    *,
    auth_key_id: str | None = None,
) -> dict[str, Any]:
    chain = _project_chain(chain_receipt)
    active, keyring = _keyring()
    key_id = auth_key_id or active
    if KEY_ID_RE.fullmatch(key_id) is None or key_id not in keyring:
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-auth-key-unavailable"
        )

    material = {
        "checkpointVersion": 1,
        "checkpointType": CHECKPOINT_TYPE,
        "witnessId": WITNESS_ID,
        "chainVersion": 1,
        "sequence": chain["sequence"],
        "previousChainTag": chain["previous_chain_tag"],
        "chainTag": chain["chain_tag"],
        "storage": CHECKPOINT_STORAGE,
    }
    serialized = _canonical_json(material)
    return {
        **material,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "authTag": _hmac_sha256(
            keyring[key_id],
            AUTH_DOMAIN + "\n" + key_id + "\n" + serialized,
        ),
    }


def verify_redis_foundation_chain_checkpoint(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-checkpoint-invalid"
        )

    required = (
        "checkpointVersion",
        "checkpointType",
        "witnessId",
        "chainVersion",
        "sequence",
        "previousChainTag",
        "chainTag",
        "storage",
        "authAlgorithm",
        "authKeyId",
        "authTag",
    )
    if any(key not in value for key in required):
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-checkpoint-invalid"
        )

    sequence = value.get("sequence")
    previous = value.get("previousChainTag")
    chain_tag = value.get("chainTag")
    key_id = value.get("authKeyId")
    auth_tag = value.get("authTag")
    if (
        value.get("checkpointVersion") != 1
        or value.get("checkpointType") != CHECKPOINT_TYPE
        or value.get("witnessId") != WITNESS_ID
        or value.get("chainVersion") != 1
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or not 1 <= sequence <= 10_000_000
        or not isinstance(previous, str)
        or SHA256_RE.fullmatch(previous) is None
        or not isinstance(chain_tag, str)
        or SHA256_RE.fullmatch(chain_tag) is None
        or value.get("storage") != CHECKPOINT_STORAGE
        or value.get("authAlgorithm") != "HMAC-SHA-256"
        or not isinstance(key_id, str)
        or KEY_ID_RE.fullmatch(key_id) is None
        or not isinstance(auth_tag, str)
        or SHA256_RE.fullmatch(auth_tag) is None
        or (sequence == 1 and previous != "0" * 64)
    ):
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-checkpoint-invalid"
        )

    material = {
        "checkpointVersion": 1,
        "checkpointType": CHECKPOINT_TYPE,
        "witnessId": WITNESS_ID,
        "chainVersion": 1,
        "sequence": sequence,
        "previousChainTag": previous,
        "chainTag": chain_tag,
        "storage": CHECKPOINT_STORAGE,
    }
    expected = _hmac_sha256(
        _secret_for(key_id),
        AUTH_DOMAIN + "\n" + key_id + "\n" + _canonical_json(material),
    )
    if not hmac.compare_digest(expected, auth_tag):
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-auth-failed"
        )

    return {key: value[key] for key in required}


def read_redis_foundation_chain_checkpoint(
    *,
    redis_client=None,
) -> dict[str, Any] | None:
    try:
        client = _redis_client(redis_client)
    except TrustStorageError as exc:
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-unavailable"
        ) from exc

    try:
        data = client.hgetall(REDIS_KEY)
    except RedisError as exc:
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-unavailable"
        ) from exc
    if not data:
        return None

    raw = data.get("checkpoint_json")
    if not isinstance(raw, str) or not raw:
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-storage-invalid"
        )
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-storage-invalid"
        ) from exc

    verified = verify_redis_foundation_chain_checkpoint(parsed)
    if (
        str(data.get("sequence") or "") != str(verified["sequence"])
        or data.get("previous_chain_tag") != verified["previousChainTag"]
        or data.get("chain_tag") != verified["chainTag"]
    ):
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-storage-mismatch"
        )
    return verified


def _matches_chain(checkpoint: dict[str, Any], chain: dict[str, Any]) -> bool:
    return (
        checkpoint.get("witnessId") == chain["witness_id"]
        and checkpoint.get("chainVersion") == chain["chain_version"]
        and checkpoint.get("sequence") == chain["sequence"]
        and checkpoint.get("previousChainTag") == chain["previous_chain_tag"]
        and checkpoint.get("chainTag") == chain["chain_tag"]
    )


def ensure_redis_foundation_chain_checkpoint(
    chain_receipt: Any,
    *,
    redis_client=None,
) -> dict[str, Any]:
    chain = _project_chain(chain_receipt)
    try:
        client = _redis_client(redis_client)
    except TrustStorageError as exc:
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-unavailable"
        ) from exc

    existing = read_redis_foundation_chain_checkpoint(
        redis_client=client,
    )
    if existing is not None:
        current_sequence = existing["sequence"]
        if current_sequence > chain["sequence"]:
            raise RedisFoundationChainCheckpointError(
                "foundation-chain-redis-ahead"
            )
        if current_sequence == chain["sequence"]:
            if not _matches_chain(existing, chain):
                raise RedisFoundationChainCheckpointError(
                    "foundation-chain-redis-fork"
                )
            return {
                "status": "verified",
                "checkpoint_version": 1,
                "witness_id": WITNESS_ID,
                "chain_version": 1,
                "sequence": existing["sequence"],
                "previous_chain_tag": existing["previousChainTag"],
                "chain_tag": existing["chainTag"],
                "auth_key_id": existing["authKeyId"],
                "storage": CHECKPOINT_STORAGE,
                "mode": "existing",
            }

        if chain["sequence"] != current_sequence + 1:
            raise RedisFoundationChainCheckpointError(
                "foundation-chain-redis-sequence-gap"
            )
        if chain["previous_chain_tag"] != existing["chainTag"]:
            raise RedisFoundationChainCheckpointError(
                "foundation-chain-redis-predecessor-mismatch"
            )
    elif chain["sequence"] != 1:
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-history-missing"
        )

    candidate = create_redis_foundation_chain_checkpoint(chain)
    try:
        result = client.eval(
            _CAS,
            1,
            REDIS_KEY,
            str(chain["sequence"]),
            chain["previous_chain_tag"],
            chain["chain_tag"],
            _canonical_json(candidate),
        )
    except RedisError as exc:
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-unavailable"
        ) from exc

    code = (
        str(result[0])
        if isinstance(result, (list, tuple)) and result
        else str(result or "")
    )
    if code not in {"created", "existing", "advanced"}:
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-cas-" + (code or "failed")
        )

    stored = read_redis_foundation_chain_checkpoint(
        redis_client=client,
    )
    if stored is None or not _matches_chain(stored, chain):
        raise RedisFoundationChainCheckpointError(
            "foundation-chain-redis-commit-mismatch"
        )

    return {
        "status": "verified",
        "checkpoint_version": 1,
        "witness_id": WITNESS_ID,
        "chain_version": 1,
        "sequence": stored["sequence"],
        "previous_chain_tag": stored["previousChainTag"],
        "chain_tag": stored["chainTag"],
        "auth_key_id": stored["authKeyId"],
        "storage": CHECKPOINT_STORAGE,
        "mode": code,
    }


__all__ = [
    "ACTIVE_KEY_ENV",
    "AUTH_DOMAIN",
    "CHECKPOINT_STORAGE",
    "KEYRING_ENV",
    "REDIS_KEY",
    "RedisFoundationChainCheckpointError",
    "create_redis_foundation_chain_checkpoint",
    "ensure_redis_foundation_chain_checkpoint",
    "read_redis_foundation_chain_checkpoint",
    "verify_redis_foundation_chain_checkpoint",
]
