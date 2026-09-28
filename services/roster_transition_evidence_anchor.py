"""Independent Redis anchor for external-roster transition evidence."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from typing import Any

from redis.exceptions import RedisError
from services.shine_trust_storage import TrustStorageError, _redis_client

SHA256_RE=re.compile(r"^[a-f0-9]{64}$")
KEY_ID_RE=re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
REDIS_KEY="shine:project-l:external-roster-transition-evidence:anchor:v1"
KEYRING_ENV="SHINE_TRACE_EXTERNAL_ROSTER_EVIDENCE_REDIS_KEYRING_JSON"
ACTIVE_KEY_ENV="SHINE_TRACE_EXTERNAL_ROSTER_EVIDENCE_REDIS_ACTIVE_KEY_ID"
AUTH_DOMAIN="shine:project-l:external-roster-transition-evidence:redis:v1"

_CAS=r"""
local key=KEYS[1]
local generation=tonumber(ARGV[1])
local evidence_sha=ARGV[2]
local anchor_json=ARGV[3]
local current_raw=redis.call('HGET',key,'generation')
if not current_raw then
  if generation ~= 2 then return {'genesis-generation-invalid'} end
  redis.call('HSET',key,'generation',tostring(generation),
    'evidence_sha256',evidence_sha,'anchor_json',anchor_json)
  return {'created'}
end
local current=tonumber(current_raw)
local current_sha=redis.call('HGET',key,'evidence_sha256') or ''
if generation < current then return {'rollback'} end
if generation == current then
  if evidence_sha ~= current_sha then return {'equivocation'} end
  return {'existing'}
end
if generation ~= current+1 then return {'generation-gap'} end
redis.call('HSET',key,'generation',tostring(generation),
  'evidence_sha256',evidence_sha,'anchor_json',anchor_json)
return {'advanced'}
"""

class RosterEvidenceAnchorError(RuntimeError):
    pass

def _canonical(v): return json.dumps(v,ensure_ascii=False,separators=(",",":"))

def _keyring():
    raw=os.getenv(KEYRING_ENV,"").strip()
    active=os.getenv(ACTIVE_KEY_ENV,"").strip()
    try: parsed=json.loads(raw)
    except Exception as exc:
        raise RosterEvidenceAnchorError("roster-evidence-anchor-keyring-invalid") from exc
    if (not isinstance(parsed,dict) or KEY_ID_RE.fullmatch(active) is None
        or active not in parsed or not isinstance(parsed[active],str)
        or len(parsed[active])<32):
        raise RosterEvidenceAnchorError("roster-evidence-anchor-keyring-unavailable")
    return active,parsed

def evidence_digest(evidence: Any) -> str:
    if not isinstance(evidence,dict) or evidence.get("status")!="verified":
        raise RosterEvidenceAnchorError("roster-evidence-anchor-evidence-invalid")
    generation=evidence.get("generation")
    auth_sha=evidence.get("authorizationSha256")
    previous=evidence.get("previousPolicySha256")
    policy=evidence.get("policySha256")
    ids=evidence.get("authorizingWitnessIds")
    if (not isinstance(generation,int) or isinstance(generation,bool) or generation<2
        or not isinstance(auth_sha,str) or SHA256_RE.fullmatch(auth_sha) is None
        or not isinstance(previous,str) or SHA256_RE.fullmatch(previous) is None
        or not isinstance(policy,str) or SHA256_RE.fullmatch(policy) is None
        or not isinstance(ids,list) or not 2<=len(ids)<=4
        or len(ids)!=len(set(ids))):
        raise RosterEvidenceAnchorError("roster-evidence-anchor-evidence-invalid")
    material={"generation":generation,"previousPolicySha256":previous,
      "policySha256":policy,"authorizationSha256":auth_sha,
      "authorizingWitnessIds":sorted(ids)}
    return hashlib.sha256(_canonical(material).encode()).hexdigest()

def _create(evidence):
    active,keyring=_keyring()
    digest=evidence_digest(evidence)
    material={"anchorVersion":1,"generation":evidence["generation"],
      "evidenceSha256":digest,"storage":"railway-redis-volume"}
    tag=hmac.new(keyring[active].encode(),
      (AUTH_DOMAIN+"\n"+active+"\n"+_canonical(material)).encode(),
      hashlib.sha256).hexdigest()
    return {**material,"authAlgorithm":"HMAC-SHA-256",
      "authKeyId":active,"authTag":tag}

def _verify(anchor):
    active,keyring=_keyring()
    if not isinstance(anchor,dict): raise RosterEvidenceAnchorError("roster-evidence-anchor-invalid")
    key_id=anchor.get("authKeyId")
    material={"anchorVersion":anchor.get("anchorVersion"),
      "generation":anchor.get("generation"),"evidenceSha256":anchor.get("evidenceSha256"),
      "storage":anchor.get("storage")}
    if (material["anchorVersion"]!=1 or not isinstance(material["generation"],int)
        or material["generation"]<2 or not isinstance(material["evidenceSha256"],str)
        or SHA256_RE.fullmatch(material["evidenceSha256"]) is None
        or material["storage"]!="railway-redis-volume"
        or anchor.get("authAlgorithm")!="HMAC-SHA-256"
        or not isinstance(key_id,str) or key_id not in keyring
        or not isinstance(anchor.get("authTag"),str)):
        raise RosterEvidenceAnchorError("roster-evidence-anchor-invalid")
    expected=hmac.new(keyring[key_id].encode(),
      (AUTH_DOMAIN+"\n"+key_id+"\n"+_canonical(material)).encode(),
      hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,anchor["authTag"]):
        raise RosterEvidenceAnchorError("roster-evidence-anchor-auth-failed")
    return anchor

def read_roster_evidence_anchor(*,redis_client=None):
    try: client=_redis_client(redis_client); row=client.hgetall(REDIS_KEY)
    except (TrustStorageError,RedisError) as exc:
        raise RosterEvidenceAnchorError("roster-evidence-anchor-unavailable") from exc
    if not row: return None
    try: anchor=json.loads(row["anchor_json"])
    except Exception as exc: raise RosterEvidenceAnchorError("roster-evidence-anchor-storage-invalid") from exc
    _verify(anchor)
    if (str(anchor["generation"])!=str(row.get("generation"))
        or anchor["evidenceSha256"]!=row.get("evidence_sha256")):
        raise RosterEvidenceAnchorError("roster-evidence-anchor-storage-mismatch")
    return anchor

def ensure_roster_evidence_anchor(evidence,*,redis_client=None):
    digest=evidence_digest(evidence)
    existing=read_roster_evidence_anchor(redis_client=redis_client)
    if existing:
        if existing["generation"]>evidence["generation"]:
            raise RosterEvidenceAnchorError("roster-evidence-anchor-ahead")
        if existing["generation"]==evidence["generation"]:
            if existing["evidenceSha256"]!=digest:
                raise RosterEvidenceAnchorError("roster-evidence-anchor-fork")
            return {"status":"verified","mode":"existing",**existing}
        if evidence["generation"]!=existing["generation"]+1:
            raise RosterEvidenceAnchorError("roster-evidence-anchor-generation-gap")
    elif evidence["generation"]!=2:
        raise RosterEvidenceAnchorError("roster-evidence-anchor-history-missing")
    candidate=_create(evidence)
    try:
        client=_redis_client(redis_client)
        result=client.eval(_CAS,1,REDIS_KEY,str(evidence["generation"]),
          digest,_canonical(candidate))
    except (TrustStorageError,RedisError) as exc:
        raise RosterEvidenceAnchorError("roster-evidence-anchor-unavailable") from exc
    code=str(result[0]) if isinstance(result,(list,tuple)) and result else str(result or "")
    if code not in {"created","existing","advanced"}:
        raise RosterEvidenceAnchorError("roster-evidence-anchor-cas-"+(code or "failed"))
    stored=read_roster_evidence_anchor(redis_client=client)
    if stored is None or stored["generation"]!=evidence["generation"] or stored["evidenceSha256"]!=digest:
        raise RosterEvidenceAnchorError("roster-evidence-anchor-commit-mismatch")
    return {"status":"verified","mode":code,**stored}
