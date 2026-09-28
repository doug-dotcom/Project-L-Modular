"""Independent Redis high-water mirror for roster transition evidence."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from typing import Any

from redis import Redis
from redis.exceptions import RedisError


SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
KEY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
REDIS_KEY = "shine:project-l:external-roster-transition-evidence:mirror:v1"
KEYRING_ENV = "SHINE_TRACE_EXTERNAL_ROSTER_EVIDENCE_REDIS_KEYRING_JSON"
ACTIVE_KEY_ENV = "SHINE_TRACE_EXTERNAL_ROSTER_EVIDENCE_REDIS_ACTIVE_KEY_ID"
AUTH_DOMAIN = "shine:project-l:external-roster-transition-evidence:mirror:v1"
STORAGE = "railway-redis-volume"

_CAS = r"""
local key = KEYS[1]
local generation = tonumber(ARGV[1])
local previous_policy_sha = ARGV[2]
local policy_sha = ARGV[3]
local authorization_sha = ARGV[4]
local evidence_sha = ARGV[5]
local checkpoint_json = ARGV[6]

local current_generation_raw = redis.call('HGET', key, 'generation')
if not current_generation_raw then
  if generation ~= 2 then return {'bootstrap-generation-invalid'} end
  redis.call(
    'HSET', key,
    'generation', tostring(generation),
    'previous_policy_sha256', previous_policy_sha,
    'policy_sha256', policy_sha,
    'authorization_sha256', authorization_sha,
    'evidence_sha256', evidence_sha,
    'checkpoint_json', checkpoint_json
  )
  return {'created'}
end

local current_generation = tonumber(current_generation_raw)
local current_previous = redis.call('HGET', key, 'previous_policy_sha256') or ''
local current_policy = redis.call('HGET', key, 'policy_sha256') or ''
local current_authorization = redis.call('HGET', key, 'authorization_sha256') or ''
local current_evidence = redis.call('HGET', key, 'evidence_sha256') or ''

if generation < current_generation then return {'rollback'} end

if generation == current_generation then
  if previous_policy_sha ~= current_previous then return {'fork'} end
  if policy_sha ~= current_policy then return {'fork'} end
  if authorization_sha ~= current_authorization then return {'fork'} end
  if evidence_sha ~= current_evidence then return {'fork'} end
  redis.call('HSET', key, 'checkpoint_json', checkpoint_json)
  return {'existing'}
end

if generation ~= current_generation + 1 then return {'generation-gap'} end
if previous_policy_sha ~= current_policy then return {'predecessor-policy-mismatch'} end

redis.call(
  'HSET', key,
  'generation', tostring(generation),
  'previous_policy_sha256', previous_policy_sha,
  'policy_sha256', policy_sha,
  'authorization_sha256', authorization_sha,
  'evidence_sha256', evidence_sha,
  'checkpoint_json', checkpoint_json
)
return {'advanced'}
"""


class RosterTransitionEvidenceMirrorError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hmac_sha256(secret: str, value: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _redis_client(redis_client=None):
    if redis_client is not None:
        return redis_client
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-mirror-redis-unavailable"
        )
    return Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
        health_check_interval=30,
    )


def _keyring() -> tuple[str, dict[str, str]]:
    raw = os.getenv(KEYRING_ENV, "").strip()
    active = os.getenv(ACTIVE_KEY_ENV, "").strip()
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-mirror-keyring-invalid"
        ) from exc
    if (
        not isinstance(parsed, dict)
        or not 1 <= len(parsed) <= 4
        or KEY_ID_RE.fullmatch(active) is None
        or active not in parsed
    ):
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-mirror-keyring-unavailable"
        )
    result: dict[str, str] = {}
    for raw_id, raw_secret in parsed.items():
        key_id = str(raw_id)
        if (
            KEY_ID_RE.fullmatch(key_id) is None
            or not isinstance(raw_secret, str)
            or not 32 <= len(raw_secret) <= 8192
        ):
            raise RosterTransitionEvidenceMirrorError(
                "external-roster-evidence-mirror-keyring-invalid"
            )
        result[key_id] = raw_secret
    return active, result


def project_evidence(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("status") != "verified":
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-invalid"
        )
    generation = value.get("generation")
    previous = value.get("previousPolicySha256")
    policy = value.get("policySha256")
    authorization = value.get("authorizationSha256")
    witness_ids = value.get("authorizingWitnessIds")
    authorizations = value.get("authorizations")
    if (
        not isinstance(generation, int)
        or isinstance(generation, bool)
        or generation < 2
        or not isinstance(previous, str)
        or SHA256_RE.fullmatch(previous) is None
        or not isinstance(policy, str)
        or SHA256_RE.fullmatch(policy) is None
        or not isinstance(authorization, str)
        or SHA256_RE.fullmatch(authorization) is None
        or not isinstance(witness_ids, list)
        or not 2 <= len(witness_ids) <= 4
        or witness_ids != sorted(witness_ids)
        or len(set(witness_ids)) != len(witness_ids)
        or not isinstance(authorizations, list)
        or len(authorizations) != len(witness_ids)
    ):
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-invalid"
        )
    safe_authorizations = []
    for row in authorizations:
        if (
            not isinstance(row, dict)
            or row.get("authorizationVersion") != 1
            or row.get("authorizationType")
                != "decision_trace_trust_state_external_witness_roster_transition"
            or row.get("authAlgorithm") != "HMAC-SHA-256"
            or row.get("witnessId") not in witness_ids
            or row.get("fromGeneration") != generation - 1
            or row.get("toGeneration") != generation
            or row.get("fromPolicySha256") != previous
            or row.get("toPolicySha256") != policy
            or not isinstance(row.get("authKeyId"), str)
            or KEY_ID_RE.fullmatch(row["authKeyId"]) is None
            or not isinstance(row.get("authTag"), str)
            or SHA256_RE.fullmatch(row["authTag"]) is None
        ):
            raise RosterTransitionEvidenceMirrorError(
                "external-roster-evidence-invalid"
            )
        safe_authorizations.append({
            "authorizationVersion": 1,
            "authorizationType": row["authorizationType"],
            "authAlgorithm": "HMAC-SHA-256",
            "witnessId": row["witnessId"],
            "authKeyId": row["authKeyId"],
            "fromGeneration": generation - 1,
            "toGeneration": generation,
            "fromPolicySha256": previous,
            "toPolicySha256": policy,
            "authTag": row["authTag"],
        })
    safe_authorizations.sort(key=lambda row: row["witnessId"])
    if [row["witnessId"] for row in safe_authorizations] != witness_ids:
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-invalid"
        )
    return {
        "generation": generation,
        "previousPolicySha256": previous,
        "policySha256": policy,
        "authorizationSha256": authorization,
        "authorizingWitnessIds": list(witness_ids),
        "authorizations": safe_authorizations,
    }


def digest_evidence(value: Any) -> str:
    return _sha256_text(_canonical_json(project_evidence(value)))


def _checkpoint(evidence: dict[str, Any], evidence_sha: str) -> dict[str, Any]:
    active, keyring = _keyring()
    material = {
        "checkpointVersion": 1,
        "checkpointType": "external_roster_transition_evidence_high_water",
        "generation": evidence["generation"],
        "previousPolicySha256": evidence["previousPolicySha256"],
        "policySha256": evidence["policySha256"],
        "authorizationSha256": evidence["authorizationSha256"],
        "evidenceSha256": evidence_sha,
        "storage": STORAGE,
    }
    return {
        **material,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": active,
        "authTag": _hmac_sha256(
            keyring[active],
            AUTH_DOMAIN + "\n" + active + "\n" + _canonical_json(material),
        ),
    }


def verify_checkpoint(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-mirror-checkpoint-invalid"
        )
    key_id = value.get("authKeyId")
    auth_tag = value.get("authTag")
    material = {
        "checkpointVersion": value.get("checkpointVersion"),
        "checkpointType": value.get("checkpointType"),
        "generation": value.get("generation"),
        "previousPolicySha256": value.get("previousPolicySha256"),
        "policySha256": value.get("policySha256"),
        "authorizationSha256": value.get("authorizationSha256"),
        "evidenceSha256": value.get("evidenceSha256"),
        "storage": value.get("storage"),
    }
    if (
        material["checkpointVersion"] != 1
        or material["checkpointType"]
            != "external_roster_transition_evidence_high_water"
        or not isinstance(material["generation"], int)
        or material["generation"] < 2
        or any(
            not isinstance(material[key], str)
            or SHA256_RE.fullmatch(material[key]) is None
            for key in (
                "previousPolicySha256",
                "policySha256",
                "authorizationSha256",
                "evidenceSha256",
            )
        )
        or material["storage"] != STORAGE
        or value.get("authAlgorithm") != "HMAC-SHA-256"
        or not isinstance(key_id, str)
        or KEY_ID_RE.fullmatch(key_id) is None
        or not isinstance(auth_tag, str)
        or SHA256_RE.fullmatch(auth_tag) is None
    ):
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-mirror-checkpoint-invalid"
        )
    _active, keyring = _keyring()
    secret = keyring.get(key_id)
    if secret is None:
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-mirror-key-retired"
        )
    expected = _hmac_sha256(
        secret,
        AUTH_DOMAIN + "\n" + key_id + "\n" + _canonical_json(material),
    )
    if not hmac.compare_digest(expected, auth_tag):
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-mirror-auth-failed"
        )
    return {**material, "authAlgorithm": "HMAC-SHA-256", "authKeyId": key_id, "authTag": auth_tag}


def read_mirror(*, redis_client=None) -> dict[str, Any] | None:
    client = _redis_client(redis_client)
    try:
        row = client.hgetall(REDIS_KEY)
    except RedisError as exc:
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-mirror-redis-unavailable"
        ) from exc
    if not row:
        return None
    raw = row.get("checkpoint_json")
    if not isinstance(raw, str) or not raw:
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-mirror-storage-invalid"
        )
    try:
        checkpoint = verify_checkpoint(json.loads(raw))
    except RosterTransitionEvidenceMirrorError:
        raise
    except Exception as exc:
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-mirror-storage-invalid"
        ) from exc
    fields = {
        "generation": str(checkpoint["generation"]),
        "previous_policy_sha256": checkpoint["previousPolicySha256"],
        "policy_sha256": checkpoint["policySha256"],
        "authorization_sha256": checkpoint["authorizationSha256"],
        "evidence_sha256": checkpoint["evidenceSha256"],
    }
    if any(row.get(k) != v for k, v in fields.items()):
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-mirror-storage-mismatch"
        )
    return checkpoint


def ensure_evidence_mirror(value: Any, *, redis_client=None) -> dict[str, Any]:
    evidence = project_evidence(value)
    evidence_sha = _sha256_text(_canonical_json(evidence))
    client = _redis_client(redis_client)
    current = read_mirror(redis_client=client)
    if current is not None:
        if current["generation"] > evidence["generation"]:
            raise RosterTransitionEvidenceMirrorError(
                "external-roster-evidence-mirror-ahead"
            )
        if current["generation"] == evidence["generation"]:
            if (
                current["previousPolicySha256"] != evidence["previousPolicySha256"]
                or current["policySha256"] != evidence["policySha256"]
                or current["authorizationSha256"] != evidence["authorizationSha256"]
                or current["evidenceSha256"] != evidence_sha
            ):
                raise RosterTransitionEvidenceMirrorError(
                    "external-roster-evidence-mirror-fork"
                )
            return {
                "status": "verified",
                "mode": "existing",
                "generation": evidence["generation"],
                "evidence_sha256": evidence_sha,
                "storage": STORAGE,
            }

    checkpoint = _checkpoint(evidence, evidence_sha)
    try:
        result = client.eval(
            _CAS,
            1,
            REDIS_KEY,
            str(evidence["generation"]),
            evidence["previousPolicySha256"],
            evidence["policySha256"],
            evidence["authorizationSha256"],
            evidence_sha,
            _canonical_json(checkpoint),
        )
    except RedisError as exc:
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-mirror-redis-unavailable"
        ) from exc
    code = (
        str(result[0])
        if isinstance(result, (list, tuple)) and result
        else str(result or "")
    )
    if code not in {"created", "existing", "advanced"}:
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-mirror-cas-" + (code or "failed")
        )
    stored = read_mirror(redis_client=client)
    if (
        stored is None
        or stored["generation"] != evidence["generation"]
        or stored["evidenceSha256"] != evidence_sha
    ):
        raise RosterTransitionEvidenceMirrorError(
            "external-roster-evidence-mirror-commit-mismatch"
        )
    return {
        "status": "verified",
        "mode": code,
        "generation": evidence["generation"],
        "evidence_sha256": evidence_sha,
        "storage": STORAGE,
    }


__all__ = [
    "ACTIVE_KEY_ENV",
    "KEYRING_ENV",
    "REDIS_KEY",
    "RosterTransitionEvidenceMirrorError",
    "digest_evidence",
    "ensure_evidence_mirror",
    "project_evidence",
    "read_mirror",
    "verify_checkpoint",
]
