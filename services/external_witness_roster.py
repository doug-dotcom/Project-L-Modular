"""Persisted authenticated external-witness roster for Project L.

This mirrors Shine-AI Layers 157-159 for the policy-head witness roster.
Generation 1 is an out-of-band pinned 2-of-2 roster:
  foundation-project-l + redis-project-l

Later roster generations are deliberately not accepted in this layer. A future
membership change must carry previous-external-quorum transition authority.
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

from services.foundation_roster_head_witness import (
    FoundationRosterHeadWitnessError,
    ensure_foundation_roster_head_witness,
    rotate_foundation_roster_head_witness,
)
from services.foundation_trust_witness import (
    FoundationWitnessError,
    ensure_foundation_roster_transition_authorization,
)
from services.roster_transition_evidence_mirror import (
    RosterTransitionEvidenceMirrorError,
    ensure_evidence_mirror,
)

SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
KEY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

ROSTER_POLICY_TYPE = (
    "decision_trace_trust_state_witness_quorum_policy_"
    "external_head_witness_quorum_policy"
)
CERTIFIED_GENESIS_ROSTER_SHA256 = (
    "a5c456d49e47f1be3f2a7b7ed017328"
    "844484ba05c4e6ef3212412c6361156c4"
)
CERTIFIED_GENESIS_WITNESS_IDS = [
    "foundation-project-l",
    "redis-project-l",
]

STATE_AUTH_DOMAIN = (
    "shine-ai:decision-trace-trust-state-witness-quorum-policy-"
    "external-head-witness-quorum-state:v1"
)
CHECKPOINT_AUTH_DOMAIN = (
    "shine-ai:decision-trace-trust-state-witness-quorum-policy-"
    "external-head-witness-quorum-state-checkpoint:v1"
)
ENVELOPE_TYPE = (
    "decision_trace_trust_state_witness_quorum_policy_"
    "external_head_witness_quorum_authenticated"
)
CHECKPOINT_TYPE = (
    "decision_trace_trust_state_witness_quorum_policy_"
    "external_head_witness_quorum_rollback_checkpoint"
)
REDIS_ROSTER_CHECKPOINT_KEY = (
    "shine:project-l:trace-trust:external-witness-roster:checkpoint:v1"
)
ROSTER_TRANSITION_AUTHORIZATION_TYPE = (
    "decision_trace_trust_state_external_witness_roster_transition"
)
ROSTER_TRANSITION_AUTH_DOMAIN = (
    "shine-ai:external-witness-roster-transition-authorization:v1"
)
ROSTER_CHAIN_TYPE = (
    "decision_trace_trust_state_witness_quorum_policy_"
    "external_head_witness_quorum_checkpoint_chain"
)
ROSTER_CHAIN_AUTH_DOMAIN = (
    "shine-ai:decision-trace-trust-state-witness-quorum-policy-"
    "external-head-witness-quorum-checkpoint-chain:v1"
)
ROSTER_HEAD_TYPE = (
    "decision_trace_trust_state_witness_quorum_policy_"
    "external_head_witness_quorum_monotonic_head"
)
ROSTER_HEAD_AUTH_DOMAIN = (
    "shine-ai:decision-trace-trust-state-witness-quorum-policy-"
    "external-head-witness-quorum-monotonic-head:v1"
)
FOUNDATION_WITNESS_ID = "foundation-project-l"
REDIS_WITNESS_ID = "redis-project-l"

_CHECKPOINT_CAS = r"""
local key = KEYS[1]
local generation = tonumber(ARGV[1])
local policy_sha = ARGV[2]
local state_sha = ARGV[3]
local previous_policy_sha = ARGV[4]
local checkpoint_json = ARGV[5]

local current_generation_raw = redis.call('HGET', key, 'generation')
if not current_generation_raw then
  if generation ~= 1 then return {'bootstrap-generation-invalid'} end
  redis.call(
    'HSET', key,
    'generation', tostring(generation),
    'policy_sha256', policy_sha,
    'state_sha256', state_sha,
    'checkpoint_json', checkpoint_json
  )
  return {'created'}
end

local current_generation = tonumber(current_generation_raw)
local current_policy_sha = redis.call('HGET', key, 'policy_sha256') or ''
local current_state_sha = redis.call('HGET', key, 'state_sha256') or ''

if generation < current_generation then return {'rollback'} end
if generation > current_generation + 1 then return {'generation-skip'} end

if generation == current_generation then
  if policy_sha ~= current_policy_sha then return {'equivocation'} end
  if state_sha ~= current_state_sha then return {'state-mismatch'} end
  redis.call('HSET', key, 'checkpoint_json', checkpoint_json)
  return {'refreshed'}
end

if previous_policy_sha ~= current_policy_sha then
  return {'predecessor-policy-mismatch'}
end
if policy_sha == current_policy_sha then
  return {'generation-without-policy-change'}
end
redis.call(
  'HSET', key,
  'generation', tostring(generation),
  'policy_sha256', policy_sha,
  'state_sha256', state_sha,
  'checkpoint_json', checkpoint_json
)
return {'advanced'}
"""


class ExternalWitnessRosterError(RuntimeError):
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
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_KEYRING_JSON",
        "",
    ).strip()
    active = os.getenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_ACTIVE_KEY_ID",
        "",
    ).strip()
    if not raw or KEY_ID_RE.fullmatch(active) is None:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-keyring-unavailable"
        )
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-keyring-invalid"
        ) from exc
    if not isinstance(parsed, dict) or not 1 <= len(parsed) <= 4:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-keyring-invalid"
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
            raise ExternalWitnessRosterError(
                "external-witness-roster-storage-keyring-invalid"
            )
        keyring[key_id] = raw_secret
    target_id = os.getenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_ROTATION_TARGET_KEY_ID",
        "",
    ).strip()
    target_secret = os.getenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_ROTATION_TARGET_SECRET",
        "",
    ).strip()
    if target_id or target_secret:
        if (
            KEY_ID_RE.fullmatch(target_id) is None
            or len(target_secret) < 32
            or len(target_secret) > 8192
        ):
            raise ExternalWitnessRosterError(
                "external-witness-roster-storage-rotation-target-invalid"
            )
        existing = keyring.get(target_id)
        if existing is not None and existing != target_secret:
            raise ExternalWitnessRosterError(
                "external-witness-roster-storage-rotation-target-conflict"
            )
        keyring[target_id] = target_secret

    if active not in keyring:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-active-key-unavailable"
        )
    return active, keyring


def _rotation_target_key_id() -> str | None:
    value = os.getenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_ROTATION_TARGET_KEY_ID",
        "",
    ).strip()
    return value or None


def _roster_head_witness_rotation_target_key_id() -> str | None:
    value = os.getenv(
        "SHINE_TRACE_EXTERNAL_ROSTER_HEAD_WITNESS_ROTATION_TARGET_KEY_ID",
        "",
    ).strip()
    if value and KEY_ID_RE.fullmatch(value) is None:
        raise ExternalWitnessRosterError(
            "external-roster-head-witness-rotation-target-invalid"
        )
    return value or None


def _storage_secret(key_id: str) -> str:
    _active, keyring = _storage_keyring()
    value = keyring.get(key_id)
    if value is None:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-key-retired"
        )
    return value


def _redis_client(redis_client=None):
    if redis_client is not None:
        return redis_client
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        raise ExternalWitnessRosterError(
            "external-witness-roster-checkpoint-redis-unavailable"
        )
    return Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
        health_check_interval=30,
    )


def project_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalWitnessRosterError(
            "external-witness-roster-policy-invalid"
        )
    generation = value.get("generation")
    minimum = value.get("minimumWitnesses")
    ids = value.get("acceptedWitnessIds")
    previous = value.get("previousPolicySha256")
    policy_sha = value.get("policySha256")
    if (
        value.get("policyVersion") != 1
        or value.get("policyType") != ROSTER_POLICY_TYPE
        or not isinstance(generation, int)
        or isinstance(generation, bool)
        or not 1 <= generation <= 1_000_000
        or not isinstance(minimum, int)
        or isinstance(minimum, bool)
        or not isinstance(ids, list)
        or not 2 <= len(ids) <= 4
        or ids != sorted(ids)
        or len(set(ids)) != len(ids)
        or any(
            not isinstance(item, str)
            or KEY_ID_RE.fullmatch(item) is None
            for item in ids
        )
        or minimum < 2
        or minimum > len(ids)
        or not isinstance(policy_sha, str)
        or SHA256_RE.fullmatch(policy_sha) is None
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-policy-invalid"
        )
    if generation == 1:
        if previous is not None:
            raise ExternalWitnessRosterError(
                "external-witness-roster-policy-invalid"
            )
    elif (
        not isinstance(previous, str)
        or SHA256_RE.fullmatch(previous) is None
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-policy-invalid"
        )

    material = {
        "policyVersion": 1,
        "policyType": ROSTER_POLICY_TYPE,
        "generation": generation,
        "minimumWitnesses": minimum,
        "acceptedWitnessIds": list(ids),
        "previousPolicySha256": previous,
    }
    if _sha256_text(_canonical_json(material)) != policy_sha:
        raise ExternalWitnessRosterError(
            "external-witness-roster-policy-digest-mismatch"
        )
    return {**material, "policySha256": policy_sha}


def _transition_material(
    witness_id: str,
    previous_policy: dict[str, Any],
    next_policy: dict[str, Any],
) -> dict[str, Any]:
    return {
        "authorizationVersion": 1,
        "authorizationType": ROSTER_TRANSITION_AUTHORIZATION_TYPE,
        "witnessId": witness_id,
        "fromGeneration": previous_policy["generation"],
        "toGeneration": next_policy["generation"],
        "fromPolicySha256": previous_policy["policySha256"],
        "toPolicySha256": next_policy["policySha256"],
    }


def _redis_transition_authorization(
    previous_policy: dict[str, Any],
    next_policy: dict[str, Any],
) -> dict[str, Any]:
    previous = project_policy(previous_policy)
    next_value = project_policy(next_policy)
    if (
        next_value["generation"] != previous["generation"] + 1
        or next_value["previousPolicySha256"] != previous["policySha256"]
        or REDIS_WITNESS_ID not in previous["acceptedWitnessIds"]
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-transition-invalid"
        )

    # The existing Redis witness keyring is intentionally not reused here.
    # Roster transition authority is a separate trust domain.
    raw = os.getenv(
        "SHINE_TRACE_EXTERNAL_ROSTER_TRANSITION_REDIS_KEYRING_JSON",
        "",
    ).strip()
    active = os.getenv(
        "SHINE_TRACE_EXTERNAL_ROSTER_TRANSITION_REDIS_ACTIVE_KEY_ID",
        "",
    ).strip()
    try:
        keyring = json.loads(raw)
    except Exception as exc:
        raise ExternalWitnessRosterError(
            "external-witness-roster-transition-keyring-invalid"
        ) from exc
    if (
        not isinstance(keyring, dict)
        or KEY_ID_RE.fullmatch(active) is None
        or active not in keyring
        or not isinstance(keyring[active], str)
        or len(keyring[active]) < 32
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-transition-keyring-unavailable"
        )

    base = _transition_material(
        REDIS_WITNESS_ID,
        previous,
        next_value,
    )
    return {
        **base,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": active,
        "authTag": _hmac_sha256(
            keyring[active],
            ROSTER_TRANSITION_AUTH_DOMAIN
            + "\n"
            + active
            + "\n"
            + _canonical_json(base),
        ),
    }


def _deployment_candidate() -> dict[str, Any] | None:
    raw = os.getenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_POLICY_JSON",
        "",
    ).strip()
    if not raw:
        return None
    try:
        return project_policy(json.loads(raw))
    except Exception as exc:
        if isinstance(exc, ExternalWitnessRosterError):
            raise
        raise ExternalWitnessRosterError(
            "external-witness-roster-policy-invalid"
        ) from exc


def _genesis_pin() -> str:
    value = os.getenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_GENESIS_SHA256",
        "",
    ).strip()
    if SHA256_RE.fullmatch(value) is None:
        raise ExternalWitnessRosterError(
            "external-witness-roster-genesis-pin-unavailable"
        )
    return value


def load_genesis_policy() -> dict[str, Any]:
    policy = _deployment_candidate()
    if policy is None:
        raise ExternalWitnessRosterError(
            "external-witness-roster-policy-unavailable"
        )
    pin = _genesis_pin()
    if (
        policy["generation"] != 1
        or policy["minimumWitnesses"] != 2
        or policy["acceptedWitnessIds"] != CERTIFIED_GENESIS_WITNESS_IDS
        or policy["previousPolicySha256"] is not None
        or policy["policySha256"] != pin
        or pin != CERTIFIED_GENESIS_ROSTER_SHA256
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-genesis-not-certified"
        )
    return policy


def policy_to_trust_state(policy: Any) -> dict[str, Any]:
    projected = project_policy(policy)
    return {
        "trustStateVersion": 1,
        "trustStateType": ROSTER_POLICY_TYPE,
        "generation": projected["generation"],
        "minimumWitnesses": projected["minimumWitnesses"],
        "acceptedWitnessIds": list(projected["acceptedWitnessIds"]),
        "previousPolicySha256": projected["previousPolicySha256"],
        "policySha256": projected["policySha256"],
    }


def project_trust_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalWitnessRosterError(
            "external-witness-roster-state-invalid"
        )
    return policy_to_trust_state({
        "policyVersion": 1,
        "policyType": ROSTER_POLICY_TYPE,
        "generation": value.get("generation"),
        "minimumWitnesses": value.get("minimumWitnesses"),
        "acceptedWitnessIds": value.get("acceptedWitnessIds"),
        "previousPolicySha256": value.get("previousPolicySha256"),
        "policySha256": value.get("policySha256"),
    })


def serialize_trust_state(state: Any) -> str:
    return _canonical_json(project_trust_state(state))


def digest_trust_state(state: Any) -> str:
    return _sha256_text(serialize_trust_state(state))


def create_envelope(
    state: Any,
    *,
    auth_key_id: str | None = None,
) -> dict[str, Any]:
    projected = project_trust_state(state)
    active, keyring = _storage_keyring()
    key_id = auth_key_id or active
    if KEY_ID_RE.fullmatch(key_id) is None or key_id not in keyring:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-auth-key-unavailable"
        )
    serialized = serialize_trust_state(projected)
    state_sha = _sha256_text(serialized)
    material = (
        STATE_AUTH_DOMAIN
        + "\n"
        + key_id
        + "\n"
        + state_sha
        + "\n"
        + serialized
    )
    return {
        "envelopeVersion": 1,
        "envelopeType": ENVELOPE_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "stateSha256": state_sha,
        "authTag": _hmac_sha256(keyring[key_id], material),
        "state": projected,
    }


def verify_envelope(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-envelope-invalid"
        )
    key_id = value.get("authKeyId")
    state_sha = value.get("stateSha256")
    auth_tag = value.get("authTag")
    if (
        value.get("envelopeVersion") != 1
        or value.get("envelopeType") != ENVELOPE_TYPE
        or value.get("authAlgorithm") != "HMAC-SHA-256"
        or not isinstance(key_id, str)
        or KEY_ID_RE.fullmatch(key_id) is None
        or not isinstance(state_sha, str)
        or SHA256_RE.fullmatch(state_sha) is None
        or not isinstance(auth_tag, str)
        or SHA256_RE.fullmatch(auth_tag) is None
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-envelope-invalid"
        )
    state = project_trust_state(value.get("state"))
    serialized = serialize_trust_state(state)
    actual_sha = _sha256_text(serialized)
    if not hmac.compare_digest(actual_sha, state_sha):
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-envelope-digest-mismatch"
        )
    material = (
        STATE_AUTH_DOMAIN
        + "\n"
        + key_id
        + "\n"
        + state_sha
        + "\n"
        + serialized
    )
    if not hmac.compare_digest(
        _hmac_sha256(_storage_secret(key_id), material),
        auth_tag,
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-envelope-auth-failed"
        )
    return state


def create_checkpoint(
    state: Any,
    *,
    auth_key_id: str | None = None,
) -> dict[str, Any]:
    projected = project_trust_state(state)
    active, keyring = _storage_keyring()
    key_id = auth_key_id or active
    if KEY_ID_RE.fullmatch(key_id) is None or key_id not in keyring:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-auth-key-unavailable"
        )
    state_sha = digest_trust_state(projected)
    base = {
        "checkpointVersion": 1,
        "checkpointType": CHECKPOINT_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "trustStateVersion": 1,
        "generation": projected["generation"],
        "policySha256": projected["policySha256"],
        "stateSha256": state_sha,
    }
    material = _canonical_json({
        "checkpointVersion": 1,
        "checkpointType": CHECKPOINT_TYPE,
        "trustStateVersion": 1,
        "generation": projected["generation"],
        "policySha256": projected["policySha256"],
        "stateSha256": state_sha,
    })
    return {
        **base,
        "authTag": _hmac_sha256(
            keyring[key_id],
            CHECKPOINT_AUTH_DOMAIN
            + "\n"
            + key_id
            + "\n"
            + material,
        ),
    }


def verify_checkpoint(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-checkpoint-invalid"
        )
    key_id = value.get("authKeyId")
    generation = value.get("generation")
    policy_sha = value.get("policySha256")
    state_sha = value.get("stateSha256")
    auth_tag = value.get("authTag")
    if (
        value.get("checkpointVersion") != 1
        or value.get("checkpointType") != CHECKPOINT_TYPE
        or value.get("authAlgorithm") != "HMAC-SHA-256"
        or value.get("trustStateVersion") != 1
        or not isinstance(key_id, str)
        or KEY_ID_RE.fullmatch(key_id) is None
        or not isinstance(generation, int)
        or isinstance(generation, bool)
        or not 1 <= generation <= 1_000_000
        or not isinstance(policy_sha, str)
        or SHA256_RE.fullmatch(policy_sha) is None
        or not isinstance(state_sha, str)
        or SHA256_RE.fullmatch(state_sha) is None
        or not isinstance(auth_tag, str)
        or SHA256_RE.fullmatch(auth_tag) is None
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-checkpoint-invalid"
        )
    material = _canonical_json({
        "checkpointVersion": 1,
        "checkpointType": CHECKPOINT_TYPE,
        "trustStateVersion": 1,
        "generation": generation,
        "policySha256": policy_sha,
        "stateSha256": state_sha,
    })
    if not hmac.compare_digest(
        _hmac_sha256(
            _storage_secret(key_id),
            CHECKPOINT_AUTH_DOMAIN
            + "\n"
            + key_id
            + "\n"
            + material,
        ),
        auth_tag,
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-checkpoint-auth-failed"
        )
    return {
        "checkpointVersion": 1,
        "checkpointType": CHECKPOINT_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "trustStateVersion": 1,
        "generation": generation,
        "policySha256": policy_sha,
        "stateSha256": state_sha,
        "authTag": auth_tag,
    }


def read_checkpoint(*, redis_client=None) -> dict[str, Any] | None:
    client = _redis_client(redis_client)
    try:
        data = client.hgetall(REDIS_ROSTER_CHECKPOINT_KEY)
    except RedisError as exc:
        raise ExternalWitnessRosterError(
            "external-witness-roster-checkpoint-redis-unavailable"
        ) from exc
    if not data:
        return None
    raw = data.get("checkpoint_json")
    if not isinstance(raw, str) or not raw:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-checkpoint-missing"
        )
    try:
        checkpoint = verify_checkpoint(json.loads(raw))
    except ExternalWitnessRosterError:
        raise
    except Exception as exc:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-checkpoint-invalid"
        ) from exc
    if (
        str(data.get("generation") or "")
        != str(checkpoint["generation"])
        or data.get("policy_sha256")
        != checkpoint["policySha256"]
        or data.get("state_sha256")
        != checkpoint["stateSha256"]
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-checkpoint-mismatch"
        )
    return checkpoint


def persist_checkpoint(
    state: Any,
    *,
    auth_key_id: str | None = None,
    redis_client=None,
) -> dict[str, Any]:
    projected = project_trust_state(state)
    checkpoint = create_checkpoint(
        projected,
        auth_key_id=auth_key_id,
    )
    client = _redis_client(redis_client)
    try:
        result = client.eval(
            _CHECKPOINT_CAS,
            1,
            REDIS_ROSTER_CHECKPOINT_KEY,
            str(projected["generation"]),
            projected["policySha256"],
            checkpoint["stateSha256"],
            projected["previousPolicySha256"] or "",
            _canonical_json(checkpoint),
        )
    except RedisError as exc:
        raise ExternalWitnessRosterError(
            "external-witness-roster-checkpoint-redis-unavailable"
        ) from exc
    code = (
        str(result[0])
        if isinstance(result, (list, tuple)) and result
        else str(result or "")
    )
    if code not in {"created", "refreshed", "advanced"}:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-checkpoint-cas-"
            + (code or "failed")
        )
    stored = read_checkpoint(redis_client=client)
    if (
        stored is None
        or stored["generation"] != projected["generation"]
        or stored["policySha256"] != projected["policySha256"]
        or stored["stateSha256"] != checkpoint["stateSha256"]
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-checkpoint-write-unverified"
        )
    return {
        "status": "verified",
        "mode": code,
        "generation": projected["generation"],
        "policy_sha256": projected["policySha256"],
        "state_sha256": checkpoint["stateSha256"],
        "auth_key_id": checkpoint["authKeyId"],
        "independent_retention": "railway-redis-volume",
    }


def verify_pair(
    envelope: Any,
    checkpoint: Any,
) -> dict[str, Any]:
    state = verify_envelope(envelope)
    cp = verify_checkpoint(checkpoint)
    if (
        state["generation"] != cp["generation"]
        or state["policySha256"] != cp["policySha256"]
        or digest_trust_state(state) != cp["stateSha256"]
        or envelope.get("stateSha256") != cp["stateSha256"]
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-pair-mismatch"
        )
    return state


def _history(db) -> list[dict[str, Any]]:
    try:
        result = db.rpc(
            "shine_ai_external_witness_roster_history_v1",
            {},
        ).execute()
    except Exception as exc:
        raise ExternalWitnessRosterError(
            "external-witness-roster-history-unavailable"
        ) from exc
    payload = result.data if isinstance(result.data, dict) else {}
    if payload.get("status") != "trusted":
        raise ExternalWitnessRosterError(
            str(
                payload.get("reason_code")
                or "external-witness-roster-history-invalid"
            )
        )
    history = payload.get("history")
    if (
        not isinstance(history, list)
        or not history
        or len(history) > 1_000_000
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-history-invalid"
        )
    return history


def create_roster_chain_record(
    state: Any,
    *,
    previous_checkpoint: dict[str, Any] | None = None,
    auth_key_id: str | None = None,
) -> dict[str, Any]:
    projected = project_trust_state(state)
    active, keyring = _storage_keyring()
    key_id = auth_key_id or active
    if KEY_ID_RE.fullmatch(key_id) is None or key_id not in keyring:
        raise ExternalWitnessRosterError(
            "external-witness-roster-chain-auth-key-unavailable"
        )

    sequence = 1
    previous_checkpoint_sha = None
    if previous_checkpoint is None:
        if (
            projected["generation"] != 1
            or projected["previousPolicySha256"] is not None
        ):
            raise ExternalWitnessRosterError(
                "external-witness-roster-chain-genesis-invalid"
            )
    else:
        previous = verify_roster_chain_record(previous_checkpoint)
        if (
            projected["generation"] != previous["generation"] + 1
            or projected["previousPolicySha256"]
            != previous["policySha256"]
        ):
            raise ExternalWitnessRosterError(
                "external-witness-roster-chain-continuity-invalid"
            )
        sequence = previous["sequence"] + 1
        previous_checkpoint_sha = previous["checkpointSha256"]

    record = {
        "chainVersion": 1,
        "chainType": ROSTER_CHAIN_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "sequence": sequence,
        "previousCheckpointSha256": previous_checkpoint_sha,
        "trustStateVersion": 1,
        "generation": projected["generation"],
        "previousPolicySha256": projected["previousPolicySha256"],
        "policySha256": projected["policySha256"],
        "stateSha256": digest_trust_state(projected),
    }
    material = _canonical_json({
        "chainVersion": 1,
        "chainType": ROSTER_CHAIN_TYPE,
        "sequence": record["sequence"],
        "previousCheckpointSha256":
            record["previousCheckpointSha256"],
        "trustStateVersion": 1,
        "generation": record["generation"],
        "previousPolicySha256": record["previousPolicySha256"],
        "policySha256": record["policySha256"],
        "stateSha256": record["stateSha256"],
    })
    checkpoint_sha = _sha256_text(material)
    return {
        **record,
        "checkpointSha256": checkpoint_sha,
        "authTag": _hmac_sha256(
            keyring[key_id],
            ROSTER_CHAIN_AUTH_DOMAIN
            + "\n"
            + key_id
            + "\n"
            + checkpoint_sha
            + "\n"
            + material,
        ),
    }


def verify_roster_chain_record(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalWitnessRosterError(
            "external-witness-roster-chain-record-invalid"
        )
    required = (
        "chainVersion",
        "chainType",
        "authAlgorithm",
        "authKeyId",
        "sequence",
        "previousCheckpointSha256",
        "trustStateVersion",
        "generation",
        "previousPolicySha256",
        "policySha256",
        "stateSha256",
        "checkpointSha256",
        "authTag",
    )
    if any(key not in value for key in required):
        raise ExternalWitnessRosterError(
            "external-witness-roster-chain-record-invalid"
        )
    key_id = value.get("authKeyId")
    sequence = value.get("sequence")
    generation = value.get("generation")
    previous_checkpoint = value.get("previousCheckpointSha256")
    previous_policy = value.get("previousPolicySha256")
    hashes = (
        value.get("policySha256"),
        value.get("stateSha256"),
        value.get("checkpointSha256"),
        value.get("authTag"),
    )
    if (
        value.get("chainVersion") != 1
        or value.get("chainType") != ROSTER_CHAIN_TYPE
        or value.get("authAlgorithm") != "HMAC-SHA-256"
        or not isinstance(key_id, str)
        or KEY_ID_RE.fullmatch(key_id) is None
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or not 1 <= sequence <= 1_000_000
        or value.get("trustStateVersion") != 1
        or not isinstance(generation, int)
        or isinstance(generation, bool)
        or not 1 <= generation <= 1_000_000
        or any(
            not isinstance(item, str)
            or SHA256_RE.fullmatch(item) is None
            for item in hashes
        )
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-chain-record-invalid"
        )
    if sequence == 1:
        if (
            previous_checkpoint is not None
            or generation != 1
            or previous_policy is not None
        ):
            raise ExternalWitnessRosterError(
                "external-witness-roster-chain-record-invalid"
            )
    elif (
        not isinstance(previous_checkpoint, str)
        or SHA256_RE.fullmatch(previous_checkpoint) is None
        or not isinstance(previous_policy, str)
        or SHA256_RE.fullmatch(previous_policy) is None
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-chain-record-invalid"
        )

    material = _canonical_json({
        "chainVersion": 1,
        "chainType": ROSTER_CHAIN_TYPE,
        "sequence": sequence,
        "previousCheckpointSha256": previous_checkpoint,
        "trustStateVersion": 1,
        "generation": generation,
        "previousPolicySha256": previous_policy,
        "policySha256": value["policySha256"],
        "stateSha256": value["stateSha256"],
    })
    checkpoint_sha = _sha256_text(material)
    if not hmac.compare_digest(
        checkpoint_sha,
        value["checkpointSha256"],
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-chain-digest-mismatch"
        )
    expected = _hmac_sha256(
        _storage_secret(key_id),
        ROSTER_CHAIN_AUTH_DOMAIN
        + "\n"
        + key_id
        + "\n"
        + checkpoint_sha
        + "\n"
        + material,
    )
    if not hmac.compare_digest(expected, value["authTag"]):
        raise ExternalWitnessRosterError(
            "external-witness-roster-chain-auth-failed"
        )
    return {key: value[key] for key in required}


def create_roster_monotonic_head(
    checkpoint: Any,
    *,
    auth_key_id: str | None = None,
) -> dict[str, Any]:
    record = verify_roster_chain_record(checkpoint)
    active, keyring = _storage_keyring()
    key_id = auth_key_id or active
    if KEY_ID_RE.fullmatch(key_id) is None or key_id not in keyring:
        raise ExternalWitnessRosterError(
            "external-witness-roster-head-auth-key-unavailable"
        )
    head = {
        "headVersion": 1,
        "headType": ROSTER_HEAD_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "checkpointChainVersion": 1,
        "sequence": record["sequence"],
        "checkpointSha256": record["checkpointSha256"],
        "generation": record["generation"],
        "policySha256": record["policySha256"],
        "stateSha256": record["stateSha256"],
    }
    material = _canonical_json({
        "headVersion": 1,
        "headType": ROSTER_HEAD_TYPE,
        "checkpointChainVersion": 1,
        "sequence": head["sequence"],
        "checkpointSha256": head["checkpointSha256"],
        "generation": head["generation"],
        "policySha256": head["policySha256"],
        "stateSha256": head["stateSha256"],
    })
    head_sha = _sha256_text(material)
    return {
        **head,
        "headSha256": head_sha,
        "authTag": _hmac_sha256(
            keyring[key_id],
            ROSTER_HEAD_AUTH_DOMAIN
            + "\n"
            + key_id
            + "\n"
            + head_sha
            + "\n"
            + material,
        ),
    }


def verify_roster_monotonic_head(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalWitnessRosterError(
            "external-witness-roster-head-invalid"
        )
    required = (
        "headVersion",
        "headType",
        "authAlgorithm",
        "authKeyId",
        "checkpointChainVersion",
        "sequence",
        "checkpointSha256",
        "generation",
        "policySha256",
        "stateSha256",
        "headSha256",
        "authTag",
    )
    if any(key not in value for key in required):
        raise ExternalWitnessRosterError(
            "external-witness-roster-head-invalid"
        )
    key_id = value.get("authKeyId")
    sequence = value.get("sequence")
    generation = value.get("generation")
    hashes = (
        value.get("checkpointSha256"),
        value.get("policySha256"),
        value.get("stateSha256"),
        value.get("headSha256"),
        value.get("authTag"),
    )
    if (
        value.get("headVersion") != 1
        or value.get("headType") != ROSTER_HEAD_TYPE
        or value.get("authAlgorithm") != "HMAC-SHA-256"
        or not isinstance(key_id, str)
        or KEY_ID_RE.fullmatch(key_id) is None
        or value.get("checkpointChainVersion") != 1
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or not 1 <= sequence <= 1_000_000
        or not isinstance(generation, int)
        or isinstance(generation, bool)
        or not 1 <= generation <= 1_000_000
        or any(
            not isinstance(item, str)
            or SHA256_RE.fullmatch(item) is None
            for item in hashes
        )
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-head-invalid"
        )
    material = _canonical_json({
        "headVersion": 1,
        "headType": ROSTER_HEAD_TYPE,
        "checkpointChainVersion": 1,
        "sequence": sequence,
        "checkpointSha256": value["checkpointSha256"],
        "generation": generation,
        "policySha256": value["policySha256"],
        "stateSha256": value["stateSha256"],
    })
    head_sha = _sha256_text(material)
    if not hmac.compare_digest(head_sha, value["headSha256"]):
        raise ExternalWitnessRosterError(
            "external-witness-roster-head-digest-mismatch"
        )
    expected = _hmac_sha256(
        _storage_secret(key_id),
        ROSTER_HEAD_AUTH_DOMAIN
        + "\n"
        + key_id
        + "\n"
        + head_sha
        + "\n"
        + material,
    )
    if not hmac.compare_digest(expected, value["authTag"]):
        raise ExternalWitnessRosterError(
            "external-witness-roster-head-auth-failed"
        )
    return {key: value[key] for key in required}


def build_roster_monotonic_head(db) -> dict[str, Any]:
    previous = None
    history = _history(db)
    for row in history:
        if not isinstance(row, dict):
            raise ExternalWitnessRosterError(
                "external-witness-roster-history-invalid"
            )
        state = project_trust_state({
            "trustStateVersion": 1,
            "trustStateType": ROSTER_POLICY_TYPE,
            "generation": row.get("generation"),
            "minimumWitnesses": row.get("minimumWitnesses"),
            "acceptedWitnessIds": row.get("acceptedWitnessIds"),
            "previousPolicySha256": row.get("previousPolicySha256"),
            "policySha256": row.get("policySha256"),
        })
        if digest_trust_state(state) != row.get("stateSha256"):
            raise ExternalWitnessRosterError(
                "external-witness-roster-history-state-digest-mismatch"
            )
        previous = create_roster_chain_record(
            state,
            previous_checkpoint=previous,
        )
    if previous is None:
        raise ExternalWitnessRosterError(
            "external-witness-roster-history-empty"
        )
    head = create_roster_monotonic_head(previous)
    verified = verify_roster_monotonic_head(head)
    if (
        verified["sequence"] != len(history)
        or verified["generation"] != len(history)
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-head-sequence-mismatch"
        )
    return {
        "status": "verified",
        "history_count": len(history),
        "checkpoint": previous,
        "head": head,
    }


def _snapshot(db) -> dict[str, Any]:
    try:
        result = db.rpc(
            "shine_ai_external_witness_roster_snapshot_v1",
            {},
        ).execute()
    except Exception as exc:
        raise ExternalWitnessRosterError(
            "external-witness-roster-snapshot-unavailable"
        ) from exc
    return result.data if isinstance(result.data, dict) else {}


def _transition_evidence(db, generation: int) -> dict[str, Any]:
    try:
        result = db.rpc(
            "shine_ai_external_roster_transition_evidence_v1",
            {"p_generation": generation},
        ).execute()
    except Exception as exc:
        raise ExternalWitnessRosterError(
            "external-witness-roster-transition-evidence-read-unavailable"
        ) from exc
    value = result.data if isinstance(result.data, dict) else {}
    if value.get("status") != "verified":
        raise ExternalWitnessRosterError(
            str(
                value.get("reason_code")
                or "external-witness-roster-transition-evidence-missing"
            )
        )
    return value


def _verify_transition_evidence_retention(
    db,
    state: dict[str, Any],
    *,
    redis_client=None,
) -> dict[str, Any]:
    generation = state["generation"]
    if generation == 1:
        return {
            "status": "not-applicable",
            "generation": 1,
            "evidence_sha256": None,
            "retention": None,
        }

    evidence = _transition_evidence(db, generation)
    if (
        evidence.get("previousPolicySha256")
        != state["previousPolicySha256"]
        or evidence.get("policySha256") != state["policySha256"]
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-transition-evidence-state-mismatch"
        )

    try:
        mirror = ensure_evidence_mirror(
            evidence,
            redis_client=redis_client,
        )
    except RosterTransitionEvidenceMirrorError as exc:
        raise ExternalWitnessRosterError(str(exc)) from exc

    return {
        "status": "verified",
        "generation": generation,
        "evidence_sha256": mirror["evidence_sha256"],
        "retention": mirror["storage"],
    }


def rotate_storage_authentication(
    db,
    *,
    target_key_id: str | None = None,
    redis_client=None,
) -> dict[str, Any]:
    """Re-authenticate roster storage without changing trusted roster state."""
    target = target_key_id or _rotation_target_key_id()
    if not target or KEY_ID_RE.fullmatch(target) is None:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-rotation-target-unavailable"
        )
    _active, keyring = _storage_keyring()
    if target not in keyring:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-rotation-target-unavailable"
        )

    payload = _snapshot(db)
    if str(payload.get("status") or "") != "trusted":
        raise ExternalWitnessRosterError(
            str(
                payload.get("reason_code")
                or "external-witness-roster-storage-invalid"
            )
        )
    state = project_trust_state(payload.get("trust_state"))
    envelope = {
        "envelopeVersion": 1,
        "envelopeType": ENVELOPE_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": payload.get("storage_auth_key_id"),
        "stateSha256": payload.get("state_sha256"),
        "authTag": payload.get("storage_auth_tag"),
        "state": state,
    }
    checkpoint = read_checkpoint(redis_client=redis_client)
    if checkpoint is None:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-checkpoint-missing"
        )
    verified = verify_pair(envelope, checkpoint)
    if verified != state:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-state-mismatch"
        )

    source_envelope_key = str(envelope.get("authKeyId") or "")
    source_checkpoint_key = str(checkpoint.get("authKeyId") or "")
    if source_envelope_key == target and source_checkpoint_key == target:
        return {
            "status": "verified",
            "mode": "already-rotated",
            "generation": state["generation"],
            "policy_sha256": state["policySha256"],
            "state_sha256": digest_trust_state(state),
            "source_envelope_key_id": source_envelope_key,
            "source_checkpoint_key_id": source_checkpoint_key,
            "target_key_id": target,
            "state_preserved": True,
        }

    target_envelope = create_envelope(
        state,
        auth_key_id=target,
    )
    checkpoint_receipt = persist_checkpoint(
        state,
        auth_key_id=target,
        redis_client=redis_client,
    )
    if (
        target_envelope["stateSha256"] != envelope["stateSha256"]
        or checkpoint_receipt["state_sha256"] != envelope["stateSha256"]
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-rotation-state-mismatch"
        )

    if source_envelope_key != target:
        try:
            result = db.rpc(
                "shine_ai_external_witness_roster_rotate_storage_v1",
                {
                    "p_expected_generation": state["generation"],
                    "p_expected_policy_sha256": state["policySha256"],
                    "p_expected_state_sha256": envelope["stateSha256"],
                    "p_expected_storage_auth_key_id": source_envelope_key,
                    "p_target_storage_auth_key_id": target,
                    "p_target_storage_auth_tag": target_envelope["authTag"],
                },
            ).execute()
        except Exception as exc:
            raise ExternalWitnessRosterError(
                "external-witness-roster-storage-rotation-db-failed"
            ) from exc
        rotated = result.data if isinstance(result.data, dict) else {}
        if rotated.get("status") not in {
            "rotated",
            "already_rotated",
        }:
            raise ExternalWitnessRosterError(
                "external-witness-roster-storage-rotation-db-unverified"
            )

    after = _snapshot(db)
    after_state = project_trust_state(after.get("trust_state"))
    after_envelope = {
        "envelopeVersion": 1,
        "envelopeType": ENVELOPE_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": after.get("storage_auth_key_id"),
        "stateSha256": after.get("state_sha256"),
        "authTag": after.get("storage_auth_tag"),
        "state": after_state,
    }
    after_checkpoint = read_checkpoint(redis_client=redis_client)
    if after_checkpoint is None:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-checkpoint-missing"
        )
    if (
        verify_pair(after_envelope, after_checkpoint) != state
        or after_state != state
        or after_envelope.get("authKeyId") != target
        or after_checkpoint.get("authKeyId") != target
        or after_envelope.get("stateSha256") != envelope.get("stateSha256")
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-rotation-verification-failed"
        )

    return {
        "status": "verified",
        "mode": "rotated",
        "generation": state["generation"],
        "policy_sha256": state["policySha256"],
        "state_sha256": envelope["stateSha256"],
        "source_envelope_key_id": source_envelope_key,
        "source_checkpoint_key_id": source_checkpoint_key,
        "target_key_id": target,
        "checkpoint_mode": checkpoint_receipt.get("mode"),
        "state_preserved": True,
    }


def load_persisted_external_witness_roster(
    db,
    *,
    redis_client=None,
) -> dict[str, Any]:
    payload = _snapshot(db)
    status = str(payload.get("status") or "")

    if status == "unbootstrapped":
        policy = load_genesis_policy()
        state = policy_to_trust_state(policy)
        envelope = create_envelope(state)
        checkpoint = persist_checkpoint(
            state,
            redis_client=redis_client,
        )
        try:
            result = db.rpc(
                "shine_ai_external_witness_roster_bootstrap_v1",
                {
                    "p_state_sha256": envelope["stateSha256"],
                    "p_storage_auth_key_id": envelope["authKeyId"],
                    "p_storage_auth_tag": envelope["authTag"],
                },
            ).execute()
        except Exception as exc:
            raise ExternalWitnessRosterError(
                "external-witness-roster-bootstrap-failed"
            ) from exc
        accepted = result.data if isinstance(result.data, dict) else {}
        if accepted.get("status") not in {
            "trusted",
            "already_trusted",
        }:
            raise ExternalWitnessRosterError(
                "external-witness-roster-bootstrap-unverified"
            )
        payload = _snapshot(db)
        status = str(payload.get("status") or "")
        _ = checkpoint

    if status != "trusted":
        raise ExternalWitnessRosterError(
            str(
                payload.get("reason_code")
                or "external-witness-roster-storage-invalid"
            )
        )

    state = project_trust_state(payload.get("trust_state"))
    envelope = {
        "envelopeVersion": 1,
        "envelopeType": ENVELOPE_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": payload.get("storage_auth_key_id"),
        "stateSha256": payload.get("state_sha256"),
        "authTag": payload.get("storage_auth_tag"),
        "state": state,
    }
    checkpoint = read_checkpoint(redis_client=redis_client)
    if checkpoint is None:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-checkpoint-missing"
        )
    verified = verify_pair(envelope, checkpoint)
    if verified != state:
        raise ExternalWitnessRosterError(
            "external-witness-roster-storage-state-mismatch"
        )

    policy = {
        "policyVersion": 1,
        "policyType": ROSTER_POLICY_TYPE,
        "generation": state["generation"],
        "minimumWitnesses": state["minimumWitnesses"],
        "acceptedWitnessIds": list(state["acceptedWitnessIds"]),
        "previousPolicySha256": state["previousPolicySha256"],
        "policySha256": state["policySha256"],
    }

    candidate = _deployment_candidate()
    if candidate is not None:
        if candidate["generation"] < state["generation"]:
            raise ExternalWitnessRosterError(
                "external-witness-roster-rollback-detected"
            )
        if candidate["generation"] == state["generation"]:
            if candidate != policy:
                raise ExternalWitnessRosterError(
                    "external-witness-roster-equivocation-detected"
                )
        elif candidate["generation"] > state["generation"] + 1:
            raise ExternalWitnessRosterError(
                "external-witness-roster-generation-skip"
            )
        else:
            redis_authorization = _redis_transition_authorization(
                policy,
                candidate,
            )
            try:
                foundation_authorization = (
                    ensure_foundation_roster_transition_authorization(
                        db,
                        policy,
                        candidate,
                    )
                )
            except FoundationWitnessError as exc:
                raise ExternalWitnessRosterError(str(exc)) from exc

            authorizations = sorted(
                [redis_authorization, foundation_authorization],
                key=lambda row: row["witnessId"],
            )
            witness_ids = [row["witnessId"] for row in authorizations]
            if (
                len(witness_ids) != len(set(witness_ids))
                or any(
                    witness_id not in policy["acceptedWitnessIds"]
                    for witness_id in witness_ids
                )
                or len(witness_ids) < policy["minimumWitnesses"]
            ):
                raise ExternalWitnessRosterError(
                    "external-witness-roster-transition-authorizations-insufficient"
                )

            next_state = policy_to_trust_state(candidate)
            next_envelope = create_envelope(next_state)
            # Redis checkpoint advances first; Supabase then commits the same
            # state. If the DB write fails, the higher Redis high-water causes
            # subsequent old-state reads to fail closed rather than roll back.
            checkpoint_receipt = persist_checkpoint(
                next_state,
                redis_client=redis_client,
            )
            authorization_sha = _sha256_text(
                _canonical_json(authorizations)
            )
            try:
                result = db.rpc(
                    "shine_ai_external_witness_roster_advance_v2",
                    {
                        "p_expected_generation": policy["generation"],
                        "p_expected_policy_sha256": policy["policySha256"],
                        "p_next_generation": candidate["generation"],
                        "p_next_minimum_witnesses":
                            candidate["minimumWitnesses"],
                        "p_next_accepted_witness_ids":
                            candidate["acceptedWitnessIds"],
                        "p_next_previous_policy_sha256":
                            candidate["previousPolicySha256"],
                        "p_next_policy_sha256":
                            candidate["policySha256"],
                        "p_authorizing_witness_ids": witness_ids,
                        "p_authorization_sha256": authorization_sha,
                        "p_state_sha256": next_envelope["stateSha256"],
                        "p_storage_auth_key_id":
                            next_envelope["authKeyId"],
                        "p_storage_auth_tag": next_envelope["authTag"],
                    },
                ).execute()
            except Exception as exc:
                raise ExternalWitnessRosterError(
                    "external-witness-roster-transition-commit-failed"
                ) from exc
            advanced = result.data if isinstance(result.data, dict) else {}
            if advanced.get("status") != "trusted":
                raise ExternalWitnessRosterError(
                    str(
                        advanced.get("reason_code")
                        or "external-witness-roster-transition-unverified"
                    )
                )
            try:
                evidence_result = db.rpc(
                    "shine_ai_external_roster_transition_evidence_record_v1",
                    {
                        "p_generation": candidate["generation"],
                        "p_previous_policy_sha256":
                            candidate["previousPolicySha256"],
                        "p_policy_sha256": candidate["policySha256"],
                        "p_authorization_sha256": authorization_sha,
                        "p_authorizing_witness_ids": witness_ids,
                        "p_authorizations": authorizations,
                    },
                ).execute()
            except Exception as exc:
                raise ExternalWitnessRosterError(
                    "external-witness-roster-transition-evidence-unavailable"
                ) from exc
            evidence = (
                evidence_result.data
                if isinstance(evidence_result.data, dict)
                else {}
            )
            if evidence.get("status") != "verified":
                raise ExternalWitnessRosterError(
                    str(
                        evidence.get("reason_code")
                        or "external-witness-roster-transition-evidence-unverified"
                    )
                )
            evidence_value = _transition_evidence(
                db,
                candidate["generation"],
            )
            try:
                ensure_evidence_mirror(
                    evidence_value,
                    redis_client=redis_client,
                )
            except RosterTransitionEvidenceMirrorError as exc:
                raise ExternalWitnessRosterError(str(exc)) from exc

            payload = _snapshot(db)
            state = project_trust_state(payload.get("trust_state"))
            if state != next_state:
                raise ExternalWitnessRosterError(
                    "external-witness-roster-transition-final-state-mismatch"
                )
            envelope = {
                "envelopeVersion": 1,
                "envelopeType": ENVELOPE_TYPE,
                "authAlgorithm": "HMAC-SHA-256",
                "authKeyId": payload.get("storage_auth_key_id"),
                "stateSha256": payload.get("state_sha256"),
                "authTag": payload.get("storage_auth_tag"),
                "state": state,
            }
            checkpoint = read_checkpoint(redis_client=redis_client)
            if checkpoint is None or verify_pair(envelope, checkpoint) != state:
                raise ExternalWitnessRosterError(
                    "external-witness-roster-transition-storage-unverified"
                )
            policy = candidate
            _ = checkpoint_receipt

    evidence_retention = _verify_transition_evidence_retention(
        db,
        state,
        redis_client=redis_client,
    )

    target = _rotation_target_key_id()
    rotation_receipt = None
    if target and (
        envelope.get("authKeyId") != target
        or checkpoint.get("authKeyId") != target
    ):
        rotation_receipt = rotate_storage_authentication(
            db,
            target_key_id=target,
            redis_client=redis_client,
        )
        payload = _snapshot(db)
        state = project_trust_state(payload.get("trust_state"))
        envelope = {
            "envelopeVersion": 1,
            "envelopeType": ENVELOPE_TYPE,
            "authAlgorithm": "HMAC-SHA-256",
            "authKeyId": payload.get("storage_auth_key_id"),
            "stateSha256": payload.get("state_sha256"),
            "authTag": payload.get("storage_auth_tag"),
            "state": state,
        }
        checkpoint = read_checkpoint(redis_client=redis_client)
        if checkpoint is None or verify_pair(envelope, checkpoint) != state:
            raise ExternalWitnessRosterError(
                "external-witness-roster-storage-rotation-verification-failed"
            )

    safe_rotation = (
        {
            "status": rotation_receipt.get("status"),
            "mode": rotation_receipt.get("mode"),
            "generation": rotation_receipt.get("generation"),
            "policy_sha256": rotation_receipt.get("policy_sha256"),
            "state_sha256": rotation_receipt.get("state_sha256"),
            "source_envelope_auth_key_id":
                rotation_receipt.get("source_envelope_key_id"),
            "source_checkpoint_auth_key_id":
                rotation_receipt.get("source_checkpoint_key_id"),
            "target_auth_key_id":
                rotation_receipt.get("target_key_id"),
            "checkpoint_mode": rotation_receipt.get("checkpoint_mode"),
            "state_preserved":
                rotation_receipt.get("state_preserved") is True,
        }
        if isinstance(rotation_receipt, dict)
        else {
            "status": "verified",
            "mode": "not-needed",
            "generation": state["generation"],
            "policy_sha256": state["policySha256"],
            "state_sha256": envelope["stateSha256"],
            "source_envelope_auth_key_id": envelope["authKeyId"],
            "source_checkpoint_auth_key_id": checkpoint["authKeyId"],
            "target_auth_key_id": envelope["authKeyId"],
            "checkpoint_mode": "existing-checkpoint",
            "state_preserved": True,
        }
    )

    head_bundle = build_roster_monotonic_head(db)
    head = head_bundle.get("head")
    if (
        not isinstance(head, dict)
        or head.get("generation") != state["generation"]
        or head.get("policySha256") != state["policySha256"]
        or head.get("stateSha256") != envelope["stateSha256"]
    ):
        raise ExternalWitnessRosterError(
            "external-witness-roster-head-state-mismatch"
        )
    try:
        foundation_head_witness = ensure_foundation_roster_head_witness(
            db,
            head,
        )
    except FoundationRosterHeadWitnessError as exc:
        raise ExternalWitnessRosterError(str(exc)) from exc

    witness_rotation_target = _roster_head_witness_rotation_target_key_id()
    witness_rotation = None
    if (
        witness_rotation_target
        and foundation_head_witness["auth_key_id"]
            != witness_rotation_target
    ):
        try:
            witness_rotation = rotate_foundation_roster_head_witness(
                db,
                witness_rotation_target,
            )
        except FoundationRosterHeadWitnessError as exc:
            raise ExternalWitnessRosterError(str(exc)) from exc
        foundation_head_witness = witness_rotation["witness"]

    safe_witness_rotation = (
        {
            "status": witness_rotation.get("status"),
            "mode": witness_rotation.get("mode"),
            "source_auth_key_id":
                witness_rotation.get("source_auth_key_id"),
            "target_auth_key_id":
                witness_rotation.get("target_auth_key_id"),
            "sequence": witness_rotation.get("sequence"),
            "head_sha256": witness_rotation.get("head_sha256"),
            "generation": witness_rotation.get("generation"),
            "policy_sha256": witness_rotation.get("policy_sha256"),
            "state_sha256": witness_rotation.get("state_sha256"),
            "state_preserved":
                witness_rotation.get("state_preserved") is True,
        }
        if isinstance(witness_rotation, dict)
        else {
            "status": "verified",
            "mode": "not-needed",
            "source_auth_key_id":
                foundation_head_witness["auth_key_id"],
            "target_auth_key_id":
                foundation_head_witness["auth_key_id"],
            "sequence": foundation_head_witness["sequence"],
            "head_sha256": foundation_head_witness["head_sha256"],
            "generation": foundation_head_witness["generation"],
            "policy_sha256": foundation_head_witness["policy_sha256"],
            "state_sha256": foundation_head_witness["state_sha256"],
            "state_preserved": True,
        }
    )

    return {
        **policy,
        "roster_trust_persisted": True,
        "roster_trust_source": "project-l-supabase",
        "roster_storage_authenticated": True,
        "roster_storage_auth_key_id": envelope["authKeyId"],
        "roster_storage_state_sha256": envelope["stateSha256"],
        "roster_storage_checkpoint_independent": True,
        "roster_storage_checkpoint_retention": "railway-redis-volume",
        "roster_storage_rotation_supported": True,
        "roster_storage_rotation_mode": safe_rotation["mode"],
        "roster_storage_rotation": safe_rotation,
        "roster_transition_evidence_status":
            evidence_retention["status"],
        "roster_transition_evidence_generation":
            evidence_retention["generation"],
        "roster_transition_evidence_sha256":
            evidence_retention["evidence_sha256"],
        "roster_transition_evidence_retention":
            evidence_retention["retention"],
        "roster_head_verified": True,
        "roster_head_sequence": head["sequence"],
        "roster_head_checkpoint_sha256": head["checkpointSha256"],
        "roster_head_sha256": head["headSha256"],
        "roster_head_generation": head["generation"],
        "roster_head_policy_sha256": head["policySha256"],
        "roster_head_state_sha256": head["stateSha256"],
        "roster_head_witness_verified":
            foundation_head_witness["status"] == "verified",
        "roster_head_witness_id":
            foundation_head_witness["witness_id"],
        "roster_head_witness_auth_key_id":
            foundation_head_witness["auth_key_id"],
        "roster_head_witness_replayed":
            foundation_head_witness["replayed"],
        "roster_head_witness_independent_retention":
            foundation_head_witness["independent_retention"],
        "roster_head_witness_rotation_supported": True,
        "roster_head_witness_rotation_mode":
            safe_witness_rotation["mode"],
        "roster_head_witness_rotation": safe_witness_rotation,
    }


__all__ = [
    "CERTIFIED_GENESIS_ROSTER_SHA256",
    "CERTIFIED_GENESIS_WITNESS_IDS",
    "CHECKPOINT_AUTH_DOMAIN",
    "ENVELOPE_TYPE",
    "ExternalWitnessRosterError",
    "REDIS_ROSTER_CHECKPOINT_KEY",
    "ROSTER_POLICY_TYPE",
    "STATE_AUTH_DOMAIN",
    "build_roster_monotonic_head",
    "create_checkpoint",
    "create_envelope",
    "create_roster_chain_record",
    "create_roster_monotonic_head",
    "digest_trust_state",
    "load_genesis_policy",
    "load_persisted_external_witness_roster",
    "persist_checkpoint",
    "policy_to_trust_state",
    "project_policy",
    "project_trust_state",
    "read_checkpoint",
    "rotate_storage_authentication",
    "serialize_trust_state",
    "verify_checkpoint",
    "verify_envelope",
    "verify_pair",
    "verify_roster_chain_record",
    "verify_roster_monotonic_head",
]
