import json
import pytest
from services import roster_transition_evidence_anchor as anchor

class R:
 def __init__(self): self.row={}
 def hgetall(self,key): return dict(self.row)
 def eval(self,_s,_n,_k,*args):
  g=int(args[0]); sha=args[1]; raw=args[2]
  if not self.row:
   if g!=2:return ["genesis-generation-invalid"]
   self.row={"generation":str(g),"evidence_sha256":sha,"anchor_json":raw};return ["created"]
  c=int(self.row["generation"])
  if g<c:return ["rollback"]
  if g==c:return ["existing"] if sha==self.row["evidence_sha256"] else ["equivocation"]
  if g!=c+1:return ["generation-gap"]
  self.row={"generation":str(g),"evidence_sha256":sha,"anchor_json":raw};return ["advanced"]

@pytest.fixture(autouse=True)
def keys(monkeypatch):
 monkeypatch.setenv(anchor.KEYRING_ENV,json.dumps({"evidence-a":"E"*48}))
 monkeypatch.setenv(anchor.ACTIVE_KEY_ENV,"evidence-a")

def ev(g=2,tag="a"):
 return {"status":"verified","generation":g,"previousPolicySha256":tag*64,
  "policySha256":chr(ord(tag)+1)*64,"authorizationSha256":chr(ord(tag)+2)*64,
  "authorizingWitnessIds":["foundation-project-l","redis-project-l"]}

def test_anchor_bootstraps_at_first_transition():
 r=R(); out=anchor.ensure_roster_evidence_anchor(ev(),redis_client=r)
 assert out["mode"]=="created" and out["generation"]==2

def test_anchor_detects_same_generation_fork():
 r=R(); anchor.ensure_roster_evidence_anchor(ev(),redis_client=r)
 bad=ev();bad["authorizationSha256"]="f"*64
 with pytest.raises(anchor.RosterEvidenceAnchorError,match="fork"):
  anchor.ensure_roster_evidence_anchor(bad,redis_client=r)

def test_anchor_advances_contiguously():
 r=R();anchor.ensure_roster_evidence_anchor(ev(),redis_client=r)
 out=anchor.ensure_roster_evidence_anchor(ev(3,"d"),redis_client=r)
 assert out["mode"]=="advanced" and out["generation"]==3

def test_anchor_detects_rollback():
 r=R();anchor.ensure_roster_evidence_anchor(ev(),redis_client=r)
 anchor.ensure_roster_evidence_anchor(ev(3,"d"),redis_client=r)
 with pytest.raises(anchor.RosterEvidenceAnchorError,match="ahead"):
  anchor.ensure_roster_evidence_anchor(ev(),redis_client=r)
