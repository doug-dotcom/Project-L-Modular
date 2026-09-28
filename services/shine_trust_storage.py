"""Authenticated Shine-AI trust-state storage and independent rollback checkpoint.

The mutable trust state remains in Project L's Supabase. A separately retained
HMAC-authenticated checkpoint is stored in private Railway Redis so a rollback of
Supabase cannot silently reset the highest trusted state.

No prompts, answers, memory text, user IDs, private Ed25519 keys or HMAC secrets
are written to Redis.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from services.shine_ai_trace_verifier import digest_verification_keyset

SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
KEY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

STATE_AUTH_DOMAIN = "shine-ai:decision-trace-trust-state:v1"
CHECKPOINT_AUTH_DOMAIN = (
    "shine-ai:decision-trace-trust-state-checkpoint:v1"
)
REDIS_CHECKPOINT_KEY = "shine:project-l:trace-trust:checkpoint:v1"

_ENVELOPE_TYPE = "decision_trace_trust_state_authenticated"
_CHECKPOINT_TYPE = "decision_trace_trust_state_rollback_checkpoint"

_CHECKPOINT_CAS = r"""
local key = KEYS[1]
local expected_generation = tonumber(ARGV[1])
local expected_state_sha = ARGV[2]
local expected_keyset_sha = ARGV[3]
local next_generation = tonumber(ARGV[4])
local next_state_sha = ARGV[5]
local next_keyset_sha = ARGV[6]
local checkpoint_json = ARGV[7]

local current_generation_raw = redis.call('HGET', key, 'generation')
if not current_generation_raw then
  if expected_generation ~= 0 then
    return {'missing'}
  end
  redis.call(
    'HSET',
    key,
    'generation', tostring(next_generation),
    'state_sha256', next_state_sha,
    'keyset_sha256', next_keyset_sha,
    'checkpoint_json', checkpoint_json
  )
  return {'created'}
end

local current_generation = tonumber(current_generation_raw)
local current_state_sha = redis.call('HGET', key, 'state_sha256') or ''
local current_keyset_sha = redis.call('HGET', key, 'keyset_sha256') or ''

if current_generation ~= expected_generation then
  return {'precondition-generation', tostring(current_generation)}
end
if current_state_sha ~= expected_state_sha then
  return {'precondition-state', current_state_sha}
end
if current_keyset_sha ~= expected_keyset_sha then
  return {'precondition-keyset', current_keyset_sha}
end

if next_generation < current_generation then
  return {'rollback'}
end
if next_generation > current_generation + 1 then
  return {'generation-skip'}
end
if next_generation == current_generation
   and next_keyset_sha ~= current_keyset_sha then
  return {'equivocation'}
end

redis.call(
  'HSET',
  key,
  'generation', tostring(next_generation),
  'state_sha256', next_state_sha,
  'keyset_sha256', next_keyset_sha,
  'checkpoint_json', checkpoint_json
)

if next_generation == current_generation then
  return {'refreshed'}
end
return {'advanced'}
"""


class TrustStorageError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hmac_sha256(secret: str, value: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _storage_keyring() -> tuple[str, dict[str, str]]:
    raw = os.getenv(
        "SHINE_AI_TRUST_STATE_STORAGE_KEYRING_JSON",
        "",
    ).strip()
    active = os.getenv(
        "SHINE_AI_TRUST_STATE_STORAGE_ACTIVE_KEY_ID",
        "",
    ).strip()
    if not raw or not active or KEY_ID_RE.fullmatch(active) is None:
        raise TrustStorageError("trust-storage-keyring-unavailable")
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        raise TrustStorageError(
            "trust-storage-keyring-invalid"
        ) from exc
    if not isinstance(parsed, dict) or not 1 <= len(parsed) <= 4:
        raise TrustStorageError("trust-storage-keyring-invalid")
    keyring: dict[str, str] = {}
    for raw_key, raw_secret in parsed.items():
        key_id = str(raw_key)
        if (
            KEY_ID_RE.fullmatch(key_id) is None
            or not isinstance(raw_secret, str)
            or len(raw_secret) < 32
            or len(raw_secret) > 8192
        ):
            raise TrustStorageError("trust-storage-keyring-invalid")
        keyring[key_id] = raw_secret
    if active not in keyring:
        raise TrustStorageError("trust-storage-active-key-unavailable")
    return active, keyring


def _secret_for(key_id: str) -> str:
    _active, keyring = _storage_keyring()
    secret = keyring.get(key_id)
    if secret is None:
        raise TrustStorageError("trust-storage-auth-key-retired")
    return secret


def project_trust_state(keyset: Any) -> dict[str, Any]:
    if not isinstance(keyset, dict):
        raise TrustStorageError("trust-state-invalid")
    generation = keyset.get("generation")
    active_key_id = keyset.get("active_key_id")
    verification_keys = keyset.get("verification_keys")
    keyset_sha256 = keyset.get("keyset_sha256")
    if (
        not isinstance(generation, int)
        or isinstance(generation, bool)
        or generation < 1
        or generation > 1_000_000
        or not isinstance(active_key_id, str)
        or KEY_ID_RE.fullmatch(active_key_id) is None
        or not isinstance(verification_keys, dict)
        or not isinstance(keyset_sha256, str)
        or SHA256_RE.fullmatch(keyset_sha256) is None
    ):
        raise TrustStorageError("trust-state-invalid")

    clean_keys: dict[str, dict[str, str]] = {}
    for key_id in sorted(verification_keys):
        item = verification_keys.get(key_id)
        if (
            not isinstance(key_id, str)
            or KEY_ID_RE.fullmatch(key_id) is None
            or not isinstance(item, dict)
            or not isinstance(item.get("public_key_b64"), str)
            or not isinstance(item.get("public_key_sha256"), str)
            or SHA256_RE.fullmatch(
                item["public_key_sha256"]
            ) is None
        ):
            raise TrustStorageError("trust-state-invalid")
        clean_keys[key_id] = {
            "public_key_b64": item["public_key_b64"],
            "public_key_sha256": item["public_key_sha256"],
        }

    if active_key_id not in clean_keys:
        raise TrustStorageError("trust-state-invalid")

    projected_keyset = {
        "active_key_id": active_key_id,
        "verification_keys": clean_keys,
        "keyset_sha256": keyset_sha256,
        "generation": generation,
    }
    if digest_verification_keyset(projected_keyset) != keyset_sha256:
        raise TrustStorageError("trust-state-keyset-invalid")

    return {
        "version": 1,
        "generation": generation,
        "active_key_id": active_key_id,
        "verification_keys": clean_keys,
        "keyset_sha256": keyset_sha256,
    }


def serialize_trust_state(state: Any) -> str:
    projected = project_trust_state(state)
    return _canonical_json(projected)


def digest_trust_state(state: Any) -> str:
    return _sha256_text(serialize_trust_state(state))


def create_authenticated_envelope(
    state: Any,
    *,
    auth_key_id: str | None = None,
) -> dict[str, Any]:
    projected = project_trust_state(state)
    active, keyring = _storage_keyring()
    key_id = auth_key_id or active
    if KEY_ID_RE.fullmatch(key_id) is None or key_id not in keyring:
        raise TrustStorageError("trust-storage-auth-key-unavailable")

    serialized = serialize_trust_state(projected)
    state_sha256 = _sha256_text(serialized)
    material = (
        STATE_AUTH_DOMAIN
        + "\n"
        + key_id
        + "\n"
        + state_sha256
        + "\n"
        + serialized
    )
    return {
        "envelopeVersion": 1,
        "envelopeType": _ENVELOPE_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "stateSha256": state_sha256,
        "authTag": _hmac_sha256(keyring[key_id], material),
        "state": projected,
    }


def verify_authenticated_envelope(
    envelope: Any,
) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        raise TrustStorageError("trust-state-envelope-invalid")
    required = (
        "envelopeVersion",
        "envelopeType",
        "authAlgorithm",
        "authKeyId",
        "stateSha256",
        "authTag",
        "state",
    )
    if any(key not in envelope for key in required):
        raise TrustStorageError("trust-state-envelope-invalid")
    key_id = envelope.get("authKeyId")
    state_sha256 = envelope.get("stateSha256")
    auth_tag = envelope.get("authTag")
    if (
        envelope.get("envelopeVersion") != 1
        or envelope.get("envelopeType") != _ENVELOPE_TYPE
        or envelope.get("authAlgorithm") != "HMAC-SHA-256"
        or not isinstance(key_id, str)
        or KEY_ID_RE.fullmatch(key_id) is None
        or not isinstance(state_sha256, str)
        or SHA256_RE.fullmatch(state_sha256) is None
        or not isinstance(auth_tag, str)
        or SHA256_RE.fullmatch(auth_tag) is None
    ):
        raise TrustStorageError("trust-state-envelope-invalid")

    state = project_trust_state(envelope.get("state"))
    serialized = serialize_trust_state(state)
    computed_state_sha = _sha256_text(serialized)
    if not hmac.compare_digest(computed_state_sha, state_sha256):
        raise TrustStorageError("trust-state-envelope-digest-mismatch")
    material = (
        STATE_AUTH_DOMAIN
        + "\n"
        + key_id
        + "\n"
        + state_sha256
        + "\n"
        + serialized
    )
    expected = _hmac_sha256(_secret_for(key_id), material)
    if not hmac.compare_digest(expected, auth_tag):
        raise TrustStorageError("trust-state-envelope-auth-failed")
    return state


def create_rollback_checkpoint(
    state: Any,
    *,
    auth_key_id: str | None = None,
) -> dict[str, Any]:
    projected = project_trust_state(state)
    active, keyring = _storage_keyring()
    key_id = auth_key_id or active
    if KEY_ID_RE.fullmatch(key_id) is None or key_id not in keyring:
        raise TrustStorageError("trust-storage-auth-key-unavailable")

    state_sha256 = digest_trust_state(projected)
    checkpoint = {
        "checkpointVersion": 1,
        "checkpointType": _CHECKPOINT_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "trustStateVersion": 1,
        "generation": projected["generation"],
        "keyset_sha256": projected["keyset_sha256"],
        "stateSha256": state_sha256,
    }
    material = _canonical_json({
        "checkpointVersion": 1,
        "checkpointType": _CHECKPOINT_TYPE,
        "trustStateVersion": 1,
        "generation": projected["generation"],
        "keyset_sha256": projected["keyset_sha256"],
        "stateSha256": state_sha256,
    })
    checkpoint["authTag"] = _hmac_sha256(
        keyring[key_id],
        CHECKPOINT_AUTH_DOMAIN
        + "\n"
        + key_id
        + "\n"
        + material,
    )
    return checkpoint


def verify_rollback_checkpoint(
    checkpoint: Any,
) -> dict[str, Any]:
    if not isinstance(checkpoint, dict):
        raise TrustStorageError("trust-checkpoint-invalid")
    required = (
        "checkpointVersion",
        "checkpointType",
        "authAlgorithm",
        "authKeyId",
        "trustStateVersion",
        "generation",
        "keyset_sha256",
        "stateSha256",
        "authTag",
    )
    if any(key not in checkpoint for key in required):
        raise TrustStorageError("trust-checkpoint-invalid")

    key_id = checkpoint.get("authKeyId")
    generation = checkpoint.get("generation")
    keyset_sha256 = checkpoint.get("keyset_sha256")
    state_sha256 = checkpoint.get("stateSha256")
    auth_tag = checkpoint.get("authTag")
    if (
        checkpoint.get("checkpointVersion") != 1
        or checkpoint.get("checkpointType") != _CHECKPOINT_TYPE
        or checkpoint.get("authAlgorithm") != "HMAC-SHA-256"
        or checkpoint.get("trustStateVersion") != 1
        or not isinstance(key_id, str)
        or KEY_ID_RE.fullmatch(key_id) is None
        or not isinstance(generation, int)
        or isinstance(generation, bool)
        or generation < 1
        or generation > 1_000_000
        or not isinstance(keyset_sha256, str)
        or SHA256_RE.fullmatch(keyset_sha256) is None
        or not isinstance(state_sha256, str)
        or SHA256_RE.fullmatch(state_sha256) is None
        or not isinstance(auth_tag, str)
        or SHA256_RE.fullmatch(auth_tag) is None
    ):
        raise TrustStorageError("trust-checkpoint-invalid")

    material = _canonical_json({
        "checkpointVersion": 1,
        "checkpointType": _CHECKPOINT_TYPE,
        "trustStateVersion": 1,
        "generation": generation,
        "keyset_sha256": keyset_sha256,
        "stateSha256": state_sha256,
    })
    expected = _hmac_sha256(
        _secret_for(key_id),
        CHECKPOINT_AUTH_DOMAIN
        + "\n"
        + key_id
        + "\n"
        + material,
    )
    if not hmac.compare_digest(expected, auth_tag):
        raise TrustStorageError("trust-checkpoint-auth-failed")
    return {
        "checkpointVersion": 1,
        "checkpointType": _CHECKPOINT_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "trustStateVersion": 1,
        "generation": generation,
        "keyset_sha256": keyset_sha256,
        "stateSha256": state_sha256,
        "authTag": auth_tag,
    }


def _redis_client(redis_client=None):
    if redis_client is not None:
        return redis_client
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        raise TrustStorageError("trust-checkpoint-redis-unavailable")
    return Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
        health_check_interval=30,
    )


def read_rollback_checkpoint(*, redis_client=None) -> dict[str, Any] | None:
    client = _redis_client(redis_client)
    try:
        data = client.hgetall(REDIS_CHECKPOINT_KEY)
    except RedisError as exc:
        raise TrustStorageError(
            "trust-checkpoint-redis-unavailable"
        ) from exc
    if not data:
        return None
    raw = data.get("checkpoint_json")
    if not isinstance(raw, str) or not raw:
        raise TrustStorageError("trust-checkpoint-storage-invalid")
    try:
        checkpoint = json.loads(raw)
    except Exception as exc:
        raise TrustStorageError(
            "trust-checkpoint-storage-invalid"
        ) from exc
    verified = verify_rollback_checkpoint(checkpoint)
    if (
        str(data.get("generation") or "") != str(verified["generation"])
        or data.get("state_sha256") != verified["stateSha256"]
        or data.get("keyset_sha256") != verified["keyset_sha256"]
    ):
        raise TrustStorageError("trust-checkpoint-storage-mismatch")
    return verified


def _checkpoint_matches_state(
    checkpoint: dict[str, Any],
    state: Any,
) -> bool:
    projected = project_trust_state(state)
    return (
        checkpoint.get("generation") == projected["generation"]
        and checkpoint.get("keyset_sha256")
        == projected["keyset_sha256"]
        and checkpoint.get("stateSha256")
        == digest_trust_state(projected)
    )


def prepare_rollback_checkpoint(
    next_state: Any,
    *,
    previous_state: Any | None = None,
    allow_genesis: bool = False,
    redis_client=None,
) -> dict[str, Any]:
    """Idempotently advance the independent checkpoint before DB mutation."""
    projected_next = project_trust_state(next_state)
    client = _redis_client(redis_client)
    existing = read_rollback_checkpoint(redis_client=client)
    candidate = create_rollback_checkpoint(projected_next)

    if existing is not None and _checkpoint_matches_state(
        existing,
        projected_next,
    ):
        return {
            "status": "ready",
            "mode": "existing-checkpoint",
            "generation": projected_next["generation"],
            "keyset_sha256": projected_next["keyset_sha256"],
            "state_sha256": candidate["stateSha256"],
        }

    if existing is None:
        if not allow_genesis or projected_next["generation"] != 1:
            raise TrustStorageError("trust-checkpoint-missing")
        expected_generation = 0
        expected_state_sha = ""
        expected_keyset_sha = ""
    else:
        if previous_state is None:
            raise TrustStorageError("trust-checkpoint-precondition-missing")
        projected_previous = project_trust_state(previous_state)
        if not _checkpoint_matches_state(existing, projected_previous):
            if existing["generation"] > projected_previous["generation"]:
                raise TrustStorageError("trust-checkpoint-ahead")
            if existing["generation"] < projected_previous["generation"]:
                raise TrustStorageError("trust-checkpoint-behind")
            if (
                existing["keyset_sha256"]
                != projected_previous["keyset_sha256"]
            ):
                raise TrustStorageError(
                    "trust-checkpoint-equivocation"
                )
            raise TrustStorageError(
                "trust-checkpoint-active-observation-mismatch"
            )
        expected_generation = projected_previous["generation"]
        expected_state_sha = existing["stateSha256"]
        expected_keyset_sha = existing["keyset_sha256"]

    raw_candidate = _canonical_json(candidate)
    try:
        result = client.eval(
            _CHECKPOINT_CAS,
            1,
            REDIS_CHECKPOINT_KEY,
            str(expected_generation),
            expected_state_sha,
            expected_keyset_sha,
            str(projected_next["generation"]),
            candidate["stateSha256"],
            candidate["keyset_sha256"],
            raw_candidate,
        )
    except RedisError as exc:
        raise TrustStorageError(
            "trust-checkpoint-redis-unavailable"
        ) from exc

    if isinstance(result, (list, tuple)) and result:
        code = str(result[0])
    else:
        code = str(result or "")
    allowed = {"created", "advanced", "refreshed"}
    if code not in allowed:
        raise TrustStorageError(
            "trust-checkpoint-cas-" + (code or "failed")
        )

    stored = read_rollback_checkpoint(redis_client=client)
    if stored is None or not _checkpoint_matches_state(
        stored,
        projected_next,
    ):
        raise TrustStorageError("trust-checkpoint-write-unverified")
    return {
        "status": "ready",
        "mode": code,
        "generation": projected_next["generation"],
        "keyset_sha256": projected_next["keyset_sha256"],
        "state_sha256": candidate["stateSha256"],
    }


def verify_state_against_checkpoint(
    state: Any,
    *,
    redis_client=None,
) -> dict[str, Any]:
    projected = project_trust_state(state)
    checkpoint = read_rollback_checkpoint(
        redis_client=redis_client
    )
    if checkpoint is None:
        raise TrustStorageError("trust-checkpoint-missing")
    if checkpoint["generation"] > projected["generation"]:
        raise TrustStorageError("trust-checkpoint-rollback-detected")
    if checkpoint["generation"] < projected["generation"]:
        raise TrustStorageError("trust-checkpoint-behind")
    if checkpoint["keyset_sha256"] != projected["keyset_sha256"]:
        raise TrustStorageError("trust-checkpoint-equivocation")
    if checkpoint["stateSha256"] != digest_trust_state(projected):
        raise TrustStorageError(
            "trust-checkpoint-active-observation-rollback"
        )
    return {
        "status": "verified",
        "generation": projected["generation"],
        "keyset_sha256": projected["keyset_sha256"],
        "state_sha256": checkpoint["stateSha256"],
        "auth_key_id": checkpoint["authKeyId"],
        "independent_retention": "railway-redis-volume",
    }


__all__ = [
    "CHECKPOINT_AUTH_DOMAIN",
    "REDIS_CHECKPOINT_KEY",
    "STATE_AUTH_DOMAIN",
    "TrustStorageError",
    "create_authenticated_envelope",
    "create_rollback_checkpoint",
    "digest_trust_state",
    "prepare_rollback_checkpoint",
    "project_trust_state",
    "read_rollback_checkpoint",
    "serialize_trust_state",
    "verify_authenticated_envelope",
    "verify_rollback_checkpoint",
    "verify_state_against_checkpoint",
]
