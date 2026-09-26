#!/usr/bin/env python3
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
profile=json.loads((root/"security/shine-defence/profile.json").read_text())
registry=json.loads((root/"security/shine-defence/canonical-registry-v1.json").read_text())
registry_entries={entry["id"]:entry for entry in registry["entries"]}
memory_policy=registry_entries.get("sensitive-memory-governance")
privacy=(root/"core/cognition/memory_privacy.py").read_text()
governance=(root/"core/cognition/memory_governance.py").read_text()
provenance=(root/"memory/retrieval/provenance.py").read_text()
security=(root/"core/cognition/production_security_gate.py").read_text()
checks=[
 ("REGISTRY",registry.get("registry")=="shine-defence/canonical-registry-v1" and registry.get("version")==profile["canonical"]["registryVersion"] and profile["canonical"]["registryBlobSha"]=="d45e5da601d9d5958f61536cfda43a1389a46242" and memory_policy is not None and memory_policy["version"]==profile["canonical"]["policyVersion"] and memory_policy["blobSha"]==profile["canonical"]["policyBlobSha"]),
 ("POLICY",profile["canonical"]["policyVersion"]=="1.0.0" and profile["canonical"]["policyBlobSha"]=="109e3e1aacb88671266c72748ad2657d6d5f9df4"),
 ("PRIVACY","uninvited_high_intimacy_surface_blocked" in privacy and "minimum_necessary_disclosure" in privacy and "can_upgrade_prior_permission" in privacy),
 ("PROMOTION",'evidence_quality = 100 if carol_packet.get("source", {}).get("role") == "user" else 0' in governance and '"approved": bool(promotion.get("promote")) and evidence_quality == 100' in governance),
 ("PROVENANCE",'TRUST_RANK' in provenance and '"user": 3' in provenance and '"assistant": 1' in provenance),
 ("SECURITY",'production_security_gate' in security and '"private_memory_used": False' in security and 'production_security_report_secret_leak' in security)
]
for name,ok in checks: print(("PASS " if ok else "FAIL ")+name)
if not all(ok for _,ok in checks): raise SystemExit(1)
print("SHINE DEFENCE: PASS sensitive-memory-governance-v1 (Project L single-user scope)")
