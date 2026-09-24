"""Layer 110: exhaustive durable recovery coverage certification."""

from types import SimpleNamespace as NS

import pytest

from core.cognition.answer_authenticity import (
    ACTIVE_KEY_ID_ENV, KEY_ENV_PREFIX, SIGNING_KEY_ENV, VERIFY_KEY_IDS_ENV,
    sign_answer_provenance,
)
from core.cognition.answer_provenance import build_answer_provenance
from core.cognition.delivery_integrity import seal_chat_delivery_payload
from core.cognition.recovery_coverage_certification import (
    VERSION, load_recovery_coverage_certification, summarise_recovery_coverage,
)
from core.cognition.recovery_provenance import PROTOCOL_VERSION, mark_answer_provenance_required
from core.cognition.release_provenance import build_release_provenance

TOKEN="x"*64
KEY_ID="k2-2026-09"
KEY="K"*64
LEGACY="L"*64
CURRENT="a"*40
HISTORICAL="b"*40
REPLY="PRIVATE RECOVERY COVERAGE ANSWER"

def key_env_name(key_id):
    return KEY_ENV_PREFIX + key_id.upper().replace("-","_")

def env(commit=CURRENT):
    return {
        "RAILWAY_GIT_REPO_OWNER":"doug-dotcom",
        "RAILWAY_GIT_REPO_NAME":"Project-L-Modular",
        "RAILWAY_GIT_BRANCH":"main",
        "RAILWAY_GIT_COMMIT_SHA":commit,
        "RAILWAY_PROJECT_NAME":"profound-wonder",
        "RAILWAY_SERVICE_NAME":"Project-L-Modular",
        "RAILWAY_ENVIRONMENT_NAME":"production",
        SIGNING_KEY_ENV:LEGACY,
        ACTIVE_KEY_ID_ENV:KEY_ID,
        VERIFY_KEY_IDS_ENV:KEY_ID,
        key_env_name(KEY_ID):KEY,
    }

def install(monkeypatch, values):
    for k in env(): monkeypatch.delenv(k,raising=False)
    for k,v in values.items(): monkeypatch.setenv(k,v)

def result(request_id, commit=CURRENT):
    live=env(CURRENT)
    release=build_release_provenance(env(commit))
    model={"status":"complete","model_id":"fixture"}
    context={"version":"1","mode":"lean"}
    persistence={"status":"verified","valid":True}
    prov=build_answer_provenance(
        request_id=request_id,final_reply=REPLY,release_provenance=release,
        model_receipt=model,context_budget=context,assistant_persistence=persistence,
        release_layer=110,
    )
    auth=sign_answer_provenance(prov,environ=live)
    body={"reply":REPLY,"server":"vx","cognition":{
        "release_provenance":release,"answer_provenance":prov,
        "answer_authenticity":auth,"model_receipt":model,
        "context_budget":context,"assistant_persistence":persistence,
    }}
    body=mark_answer_provenance_required(body,protocol_version=PROTOCOL_VERSION)
    return seal_chat_delivery_payload(body,request_id=request_id)

def row(i,payload,status="ready"):
    return {"request_id":i,"created_at":"2026-09-24T00:00:00+00:00","updated_at":"2026-09-24T00:00:01+00:00","status":status,"result":payload}

def rid(n):
    return f"00000000-0000-4000-8000-{n:012d}"

def test_complete_history_certifies_current_and_historical_answers(monkeypatch):
    install(monkeypatch,env())
    rows=[row(rid(1),result(rid(1),CURRENT)),row(rid(2),result(rid(2),HISTORICAL))]
    report=summarise_recovery_coverage(rows,scan_complete=True,capped=False,current_release=build_release_provenance(env()))
    assert report["version"]==VERSION
    assert report["status"]=="complete_recoverable"
    assert report["scan_complete"] is True
    assert report["answers_observed"]==2
    assert report["certified_answers"]==2
    assert report["modern_authenticated_answers"]==2
    assert report["failed_ready_answers"]==0
    assert report["release_relationships"]["current_release"]==1
    assert report["release_relationships"]["historical_release"]==1
    assert report["coverage"]["all_ready_answers_recoverable"] is True
    assert report["coverage"]["all_observed_tasks_certified"] is True

def test_legacy_readability_is_counted_but_not_called_modern_authentication(monkeypatch):
    install(monkeypatch,env())
    legacy=seal_chat_delivery_payload({"reply":"old","server":"vx"},request_id=rid(3))
    report=summarise_recovery_coverage([row(rid(3),legacy)],scan_complete=True,capped=False,current_release=build_release_provenance(env()))
    assert report["status"]=="complete_recoverable_with_legacy"
    assert report["certified_answers"]==1
    assert report["legacy_readable_answers"]==1
    assert report["modern_authenticated_answers"]==0
    assert report["coverage"]["all_ready_answers_recoverable"] is True

def test_tampered_ready_answer_breaks_full_recovery_coverage(monkeypatch):
    install(monkeypatch,env())
    payload=result(rid(4))
    body=dict(payload); body.pop("delivery_receipt")
    cognition=dict(body["cognition"]); auth=dict(cognition["answer_authenticity"])
    auth["signature"]="0"*64; cognition["answer_authenticity"]=auth; body["cognition"]=cognition
    bad=seal_chat_delivery_payload(body,request_id=rid(4))
    report=summarise_recovery_coverage([row(rid(4),bad)],scan_complete=True,capped=False,current_release=build_release_provenance(env()))
    assert report["status"]=="complete_with_recovery_failures"
    assert report["certified_answers"]==0
    assert report["failed_ready_answers"]==1
    assert report["coverage"]["all_ready_answers_recoverable"] is False
    assert report["failure_findings"][0]["request_ref"]
    assert "answer_authenticity_signature_mismatch" in report["issue_codes"]
    assert REPLY not in str(report)
    assert rid(4) not in str(report)
    assert KEY not in str(report)

def test_incomplete_task_is_not_counted_as_failed_ready_answer(monkeypatch):
    install(monkeypatch,env())
    report=summarise_recovery_coverage([row(rid(5),None,status="running")],scan_complete=True,capped=False,current_release=build_release_provenance(env()))
    assert report["status"]=="complete_with_incomplete_tasks"
    assert report["not_ready_answers"]==1
    assert report["failed_ready_answers"]==0
    assert report["coverage"]["all_ready_answers_recoverable"] is True
    assert report["coverage"]["all_observed_tasks_certified"] is False

def test_capped_scan_never_claims_full_coverage(monkeypatch):
    install(monkeypatch,env())
    report=summarise_recovery_coverage([row(rid(6),result(rid(6)))],scan_complete=False,capped=True,current_release=build_release_provenance(env()))
    assert report["status"]=="incomplete_scan"
    assert report["scan_complete"] is False
    assert report["coverage"]["all_ready_answers_recoverable"] is False
    assert report["claims"]["durable_recovery_coverage"]=="incomplete"

def test_empty_complete_history_is_explicit(monkeypatch):
    install(monkeypatch,env())
    report=summarise_recovery_coverage([],scan_complete=True,capped=False,current_release=build_release_provenance(env()))
    assert report["status"]=="complete_no_saved_answers"
    assert report["answers_observed"]==0
    assert report["scan_complete"] is True

class Query:
    def __init__(self,rows,calls):
        self.rows=rows; self.calls=calls; self.start=0; self.end=len(rows)-1
    def select(self,x): self.calls.append(("select",x)); return self
    def eq(self,c,v): self.calls.append(("eq",c,v)); return self
    def order(self,c,desc=False): self.calls.append(("order",c,desc)); return self
    def range(self,s,e): self.calls.append(("range",s,e)); self.start=s; self.end=e; return self
    def execute(self): return NS(data=self.rows[self.start:self.end+1])
class Client:
    def __init__(self,rows): self.rows=rows; self.calls=[]
    def table(self,n): self.calls.append(("table",n)); return Query(self.rows,self.calls)

def test_loader_pages_owner_history_cold_and_read_only(monkeypatch):
    install(monkeypatch,env())
    rows=[row(rid(100+i),result(rid(100+i))) for i in range(7)]
    client=Client(rows)
    report=load_recovery_coverage_certification(client,TOKEN,page_size=3,max_rows=20)
    assert report["scan_complete"] is True
    assert report["answers_observed"]==7
    assert report["scan"]["pages_read"]==3
    assert report["scan"]["rows_read"]==7
    assert report["scan"]["read_only"] is True
    assert report["scan"]["in_process_cache_used"] is False
    assert ("range",0,2) in client.calls and ("range",3,5) in client.calls and ("range",6,8) in client.calls
    assert any(x[0]=="eq" and x[1]=="user_id" for x in client.calls)
    assert any(x[0]=="eq" and x[1]=="owner_hash" for x in client.calls)
    assert not any(x[0] in {"insert","update","delete","upsert","rpc"} for x in client.calls)

def test_loader_cap_prevents_false_complete_claim(monkeypatch):
    install(monkeypatch,env())
    rows=[row(rid(200+i),result(rid(200+i))) for i in range(6)]
    report=load_recovery_coverage_certification(Client(rows),TOKEN,page_size=2,max_rows=4)
    assert report["scan_complete"] is False
    assert report["capped"] is True
    assert report["scan"]["rows_read"]==4
    assert report["status"]=="incomplete_scan"

@pytest.mark.parametrize("page,max_rows",[(0,100),(101,100),(1.5,100),(10,0),(10,10001),(10,"100")])
def test_loader_rejects_invalid_bounds(page,max_rows):
    with pytest.raises(ValueError):
        load_recovery_coverage_certification(Client([]),TOKEN,page_size=page,max_rows=max_rows)

def test_server_endpoint_returns_privacy_safe_coverage(monkeypatch):
    from api import server
    install(monkeypatch,env())
    client=Client([row(rid(300),result(rid(300)))])
    monkeypatch.setattr(server.task_store,"client",client)
    report=server.cognition_recovery_coverage_certification(page_size=50,max_rows=1000,x_l_recovery_token=TOKEN)
    assert report["mode"]=="durable_recovery_coverage_certification"
    assert report["scan_complete"] is True
    assert report["coverage"]["all_ready_answers_recoverable"] is True
    assert report["privacy"]["answer_text_returned"] is False
    assert REPLY not in str(report)

def test_server_surfaces_layer110_recovery_coverage_readiness():
    from pathlib import Path
    source=Path("api/server.py").read_text(encoding="utf-8")
    assert '"release_layer": 110' in source
    assert '"recovery_coverage_certification_ready": True' in source
    assert '@app.get("/cognition/recovery-coverage-certification")' in source
    assert "load_recovery_coverage_certification(" in source
