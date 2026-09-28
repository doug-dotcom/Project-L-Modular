"""Independent Redis witness for the external-roster evidence-chain head.

Layer 211 verifies the full transition-evidence chain inside Project L's Supabase.
This module retains the verified chain head on the private persistent Railway
Redis volume under a separate HMAC key. Each later generation must explicitly
name the exact previously witnessed chain tag, preventing same-generation
rewrites and rewritten-history advancement.

No user data, prompts, memories, authorization secrets, or raw HMAC keys are
stored in Redis.
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


SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
KEY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

REDIS_KEY = (
    "shine:project-l:external-roster-transition-evidence:"
    "chain-witness:v1"
)
KEYRING_ENV = (
    "SHINE_TRACE_EXTERNAL_ROSTER_EVIDENCE_CHAIN_REDIS_KEYRING_JSON"
)
ACTIVE_KEY_ENV = (
    "SHINE_TRACE_EXTERNAL_ROSTER_EVIDENCE_CHAIN_REDIS_ACTIVE_KEY_ID"
)
AUTH_DOMAIN = (
    "shine:project-l:external-roster-transition-evidence-chain:"
    "witness:v1"
)
STORAGE = "railway-redis-volume"

_CAS = r"""
local key = KEYS[1]
local generation = tonumber(ARGV[1])
local rows = tonumber(ARGV[2])
local previous_chain_tag = ARGV[3]
local evidence_sha = ARGV[4]
local chain_tag = ARGV[5]
local checkpoint_json = ARGV[6]

local current_generation_raw = redis.call('HGET', key, 'generation')
if not current_generation_raw then
  if generation ~= 1 or rows ~= 0
     or previous_chain_tag ~= ''
     or evidence_sha ~= ''
     or chain_tag ~= '' then
    return {'bootstrap-invalid'}
  end
  redis.call(
    'HSET', key,
    'generation', '1',
    'rows', '0',
    'previous_chain_tag', '',
    'evidence_sha256', '',
    'chain_tag', '',
    'checkpoint_json', checkpoint_json
  )
  return {'created'}
end

local current_generation = tonumber(current_generation_raw)
local current_rows = tonumber(redis.call('HGET', key, 'rows') or '-1')
local current_previous = redis.call('HGET', key, 'previous_chain_tag') or ''
local current_evidence = redis.call('HGET', key, 'evidence_sha256') or ''
local current_chain_tag = redis.call('HGET', key, 'chain_tag') or ''

if generation < current_generation then return {'rollback'} end

if generation == current_generation then
  if rows ~= current_rows
     or previous_chain_tag ~= current_previous
     or evidence_sha ~= current_evidence
     or chain_tag ~= current_chain_tag then
    return {'fork'}
  end
  redis.call('HSET', key, 'checkpoint_json', checkpoint_json)
  return {'existing'}
end

if generation ~= current_generation + 1 then
  return {'generation-gap'}
end
if rows ~= current_rows + 1 then
  return {'row-gap'}
end
if previous_chain_tag ~= current_chain_tag then
  if current_generation == 1
     and current_chain_tag == ''
     and previous_chain_tag == string.rep('0', 64) then
    -- Generation 2 correctly extends the zero genesis predecessor.
  else
    return {'predecessor-chain-mismatch'}
  end
end
if evidence_sha == '' or chain_tag == '' then
  return {'advanced-head-missing'}
end

redis.call(
  'HSET', key,
  'generation', tostring(generation),
  'rows', tostring(rows),
  'previous_chain_tag', previous_chain_tag,
  'evidence_sha256', evidence_sha,
  'chain_tag', chain_tag,
  'checkpoint_json', checkpoint_json
)
return {'advanced'}
"""


class RosterEvidenceChainWitnessError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


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
        raise RosterEvidenceChainWitnessError(
            "external-roster-evidence-chain-witness-redis-unavailable"
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
        raise RosterEvidenceChainWitnessError(
            "external-roster-evidence-chain-witness-keyring-invalid"
        ) from exc
    if (
        not isinstance(parsed, dict)
        or not 1 <= len(parsed) <= 4
        or KEY_ID_RE.fullmatch(active) is None
        or active not in parsed
    ):
        raise RosterEvidenceChainWitnessError(
            "external-roster-evidence-chain-witness-keyring-unavailable"
        )
    keyring: dict[str, str] = {}
    for raw_id, raw_secret in parsed.items():
        key_id = str(raw_id)
        if (
            KEY_ID_RE.fullmatch(key_id) is None
            or not isinstance(raw_secret, str)
            or not 32 <= len(raw_secret) <= 8192
        ):
            raise RosterEvidenceChainWitnessError(
                "external-roster-evidence-chain-witness-keyring-invalid"
            )
        keyring[key_id] = raw_secret
    return active, keyring


def project_chain_head(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RosterEvidenceChainWitnessError(
            "external-roster-evidence-chain-witness-invalid"
        )
    status = value.get("status")
    version = value.get("chainVersion")
    generation = value.get("latestGeneration")
    rows = value.get("rows")
    previous_chain_tag = value.get("latestPreviousChainTag")
    evidence_sha = value.get("latestEvidenceSha256")
    chain_tag = value.get("latestChainTag")

    if (
        version != 1
        or not isinstance(generation, int)
        or isinstance(generation, bool)
        or generation < 1
        or generation > 1_000_000
        or not isinstance(rows, int)
        or isinstance(rows, bool)
        or rows != generation - 1
    ):
        raise RosterEvidenceChainWitnessError(
            "external-roster-evidence-chain-witness-invalid"
        )

    if generation == 1:
        if (
            status != "empty"
            or rows != 0
            or previous_chain_tag is not None
            or evidence_sha is not None
            or chain_tag is not None
        ):
            raise RosterEvidenceChainWitnessError(
                "external-roster-evidence-chain-witness-invalid"
            )
    else:
        if (
            status != "verified"
            or not isinstance(previous_chain_tag, str)
            or SHA256_RE.fullmatch(previous_chain_tag) is None
            or not isinstance(evidence_sha, str)
            or SHA256_RE.fullmatch(evidence_sha) is None
            or not isinstance(chain_tag, str)
            or SHA256_RE.fullmatch(chain_tag) is None
        ):
            raise RosterEvidenceChainWitnessError(
                "external-roster-evidence-chain-witness-invalid"
            )

    return {
        "chainVersion": 1,
        "generation": generation,
        "rows": rows,
        "previousChainTag": previous_chain_tag,
        "evidenceSha256": evidence_sha,
        "chainTag": chain_tag,
    }


def _checkpoint(head: dict[str, Any]) -> dict[str, Any]:
    active, keyring = _keyring()
    material = {
        "checkpointVersion": 1,
        "checkpointType":
            "external_roster_transition_evidence_chain_head",
        "chainVersion": 1,
        "generation": head["generation"],
        "rows": head["rows"],
        "previousChainTag": head["previousChainTag"],
        "evidenceSha256": head["evidenceSha256"],
        "chainTag": head["chainTag"],
        "storage": STORAGE,
    }
    return {
        **material,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": active,
        "authTag": _hmac_sha256(
            keyring[active],
            AUTH_DOMAIN
            + "\n"
            + active
            + "\n"
            + _canonical_json(material),
        ),
    }


def verify_checkpoint(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RosterEvidenceChainWitnessError(
            "external-roster-evidence-chain-witness-checkpoint-invalid"
        )
    material = {
        "checkpointVersion": value.get("checkpointVersion"),
        "checkpointType": value.get("checkpointType"),
        "chainVersion": value.get("chainVersion"),
        "generation": value.get("generation"),
        "rows": value.get("rows"),
        "previousChainTag": value.get("previousChainTag"),
        "evidenceSha256": value.get("evidenceSha256"),
        "chainTag": value.get("chainTag"),
        "storage": value.get("storage"),
    }
    key_id = value.get("authKeyId")
    auth_tag = value.get("authTag")
    if (
        material["checkpointVersion"] != 1
        or material["checkpointType"]
            != "external_roster_transition_evidence_chain_head"
        or material["chainVersion"] != 1
        or not isinstance(material["generation"], int)
        or material["generation"] < 1
        or not isinstance(material["rows"], int)
        or material["rows"] != material["generation"] - 1
        or material["storage"] != STORAGE
        or value.get("authAlgorithm") != "HMAC-SHA-256"
        or not isinstance(key_id, str)
        or KEY_ID_RE.fullmatch(key_id) is None
        or not isinstance(auth_tag, str)
        or SHA256_RE.fullmatch(auth_tag) is None
    ):
        raise RosterEvidenceChainWitnessError(
            "external-roster-evidence-chain-witness-checkpoint-invalid"
        )

    generation = material["generation"]
    if generation == 1:
        if any(
            material[key] is not None
            for key in (
                "previousChainTag",
                "evidenceSha256",
                "chainTag",
            )
        ):
            raise RosterEvidenceChainWitnessError(
                "external-roster-evidence-chain-witness-checkpoint-invalid"
            )
    else:
        if any(
            not isinstance(material[key], str)
            or SHA256_RE.fullmatch(material[key]) is None
            for key in (
                "previousChainTag",
                "evidenceSha256",
                "chainTag",
            )
        ):
            raise RosterEvidenceChainWitnessError(
                "external-roster-evidence-chain-witness-checkpoint-invalid"
            )

    _active, keyring = _keyring()
    secret = keyring.get(key_id)
    if secret is None:
        raise RosterEvidenceChainWitnessError(
            "external-roster-evidence-chain-witness-key-retired"
        )
    expected = _hmac_sha256(
        secret,
        AUTH_DOMAIN
        + "\n"
        + key_id
        + "\n"
        + _canonical_json(material),
    )
    if not hmac.compare_digest(expected, auth_tag):
        raise RosterEvidenceChainWitnessError(
            "external-roster-evidence-chain-witness-auth-failed"
        )
    return {
        **material,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "authTag": auth_tag,
    }


def read_chain_witness(*, redis_client=None) -> dict[str, Any] | None:
    client = _redis_client(redis_client)
    try:
        row = client.hgetall(REDIS_KEY)
    except RedisError as exc:
        raise RosterEvidenceChainWitnessError(
            "external-roster-evidence-chain-witness-redis-unavailable"
        ) from exc
    if not row:
        return None
    raw = row.get("checkpoint_json")
    if not isinstance(raw, str) or not raw:
        raise RosterEvidenceChainWitnessError(
            "external-roster-evidence-chain-witness-storage-invalid"
        )
    try:
        value = json.loads(raw)
    except Exception as exc:
        raise RosterEvidenceChainWitnessError(
            "external-roster-evidence-chain-witness-storage-invalid"
        ) from exc
    checkpoint = verify_checkpoint(value)
    expected = {
        "generation": str(checkpoint["generation"]),
        "rows": str(checkpoint["rows"]),
        "previous_chain_tag":
            checkpoint["previousChainTag"] or "",
        "evidence_sha256": checkpoint["evidenceSha256"] or "",
        "chain_tag": checkpoint["chainTag"] or "",
    }
    if any(row.get(key) != val for key, val in expected.items()):
        raise RosterEvidenceChainWitnessError(
            "external-roster-evidence-chain-witness-storage-mismatch"
        )
    return checkpoint


def ensure_chain_witness(
    value: Any,
    *,
    redis_client=None,
) -> dict[str, Any]:
    head = project_chain_head(value)
    client = _redis_client(redis_client)
    current = read_chain_witness(redis_client=client)
    if current is not None:
        if current["generation"] > head["generation"]:
            raise RosterEvidenceChainWitnessError(
                "external-roster-evidence-chain-witness-ahead"
            )
        if current["generation"] == head["generation"]:
            if (
                current["rows"] != head["rows"]
                or current["previousChainTag"]
                    != head["previousChainTag"]
                or current["evidenceSha256"]
                    != head["evidenceSha256"]
                or current["chainTag"] != head["chainTag"]
            ):
                raise RosterEvidenceChainWitnessError(
                    "external-roster-evidence-chain-witness-fork"
                )
            return {
                "status": "verified",
                "mode": "existing",
                "generation": head["generation"],
                "rows": head["rows"],
                "chain_tag": head["chainTag"],
                "evidence_sha256": head["evidenceSha256"],
                "auth_key_id": current["authKeyId"],
                "storage": STORAGE,
            }

    checkpoint = _checkpoint(head)
    try:
        result = client.eval(
            _CAS,
            1,
            REDIS_KEY,
            str(head["generation"]),
            str(head["rows"]),
            head["previousChainTag"] or "",
            head["evidenceSha256"] or "",
            head["chainTag"] or "",
            _canonical_json(checkpoint),
        )
    except RedisError as exc:
        raise RosterEvidenceChainWitnessError(
            "external-roster-evidence-chain-witness-redis-unavailable"
        ) from exc
    code = (
        str(result[0])
        if isinstance(result, (list, tuple)) and result
        else str(result or "")
    )
    if code not in {"created", "existing", "advanced"}:
        raise RosterEvidenceChainWitnessError(
            "external-roster-evidence-chain-witness-cas-"
            + (code or "failed")
        )

    stored = read_chain_witness(redis_client=client)
    if (
        stored is None
        or stored["generation"] != head["generation"]
        or stored["rows"] != head["rows"]
        or stored["previousChainTag"] != head["previousChainTag"]
        or stored["evidenceSha256"] != head["evidenceSha256"]
        or stored["chainTag"] != head["chainTag"]
    ):
        raise RosterEvidenceChainWitnessError(
            "external-roster-evidence-chain-witness-commit-mismatch"
        )
    return {
        "status": "verified",
        "mode": code,
        "generation": head["generation"],
        "rows": head["rows"],
        "chain_tag": head["chainTag"],
        "evidence_sha256": head["evidenceSha256"],
        "auth_key_id": stored["authKeyId"],
        "storage": STORAGE,
    }


__all__ = [
    "ACTIVE_KEY_ENV",
    "KEYRING_ENV",
    "REDIS_KEY",
    "RosterEvidenceChainWitnessError",
    "ensure_chain_witness",
    "project_chain_head",
    "read_chain_witness",
    "verify_checkpoint",
]
