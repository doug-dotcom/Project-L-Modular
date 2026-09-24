"""Layer 111: durable task ledger consistency audit."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest

from core.cognition.durable_task_ledger_audit import (
    VERSION, audit_task_row, load_task_ledger_audit, summarise_task_ledger,
)
from core.cognition.durable_tasks import request_hash

TOKEN="x"*64
NOW=datetime(2026,9,24,1,0,0,tzinfo=timezone.utc)
OWNER="a"*64

def rid(n): return f"00000000-0000-4000-8000-{n:012d}"

def request(n):
    return {"request_id":rid(n),"message":f"private request {n}"}

def base_row(n,status="queued"):
    req=request(n)
    return {
        "request_id":rid(n),"owner_hash":OWNER,"input_hash":request_hash(req),
        "request":req,"status":status,"checkpoint":status,
        "worker_id":None,"lease_until":None,"result":None,
        "created_at":"2026-09-24T00:00:00+00:00",
        "updated_at":"2026-09-24T00:00:01+00:00",
    }

def test_healthy_state_machine_rows_pass():
    queued=base_row(1)
    running=base_row(2,"running")
    running["checkpoint"]="generating"; running["worker_id"]=rid(900)
    running["lease_until"]=(NOW+timedelta(minutes=1)).isoformat()
    ready=base_row(3,"ready"); ready["result"]={"sealed":"fixture"}
    failed=base_row(4,"failed"); failed["result"]={"error":True}
    interrupted=base_row(5,"interrupted"); interrupted["checkpoint"]="generating"
    interrupted["worker_id"]=rid(901); interrupted["lease_until"]=(NOW-timedelta(minutes=1)).isoformat()
    for row in [queued,running,ready,failed,interrupted]:
        audit=audit_task_row(row,now=NOW)
        assert audit["valid"] is True, audit

def test_request_hash_and_request_id_binding_tamper_are_detected():
    row=base_row(10)
    row["request"]["message"]="changed after hash"
    row["request"]["request_id"]=rid(11)
    audit=audit_task_row(row,now=NOW)
    assert audit["valid"] is False
    assert "request_hash_mismatch" in audit["issues"]
    assert "request_id_binding_mismatch" in audit["issues"]

def test_expired_running_lease_and_missing_worker_are_detected():
    row=base_row(12,"running")
    row["checkpoint"]="generating"
    row["lease_until"]=(NOW-timedelta(seconds=1)).isoformat()
    audit=audit_task_row(row,now=NOW)
    assert "running_task_missing_worker" in audit["issues"]
    assert "running_task_lease_expired" in audit["issues"]

def test_terminal_contract_and_timestamp_order_are_checked():
    row=base_row(13,"ready")
    row["checkpoint"]="generating"
    row["result"]=None
    row["updated_at"]="2026-09-23T23:59:59+00:00"
    audit=audit_task_row(row,now=NOW)
    assert "terminal_checkpoint_mismatch" in audit["issues"]
    assert "terminal_result_missing_or_malformed" in audit["issues"]
    assert "updated_before_created" in audit["issues"]

def test_queued_and_interrupted_impossible_shapes_are_detected():
    queued=base_row(14)
    queued["worker_id"]=rid(800); queued["lease_until"]=(NOW+timedelta(minutes=1)).isoformat()
    queued["result"]={"unexpected":True}
    qa=audit_task_row(queued,now=NOW)
    assert "queued_task_has_worker" in qa["issues"]
    assert "queued_task_has_lease" in qa["issues"]
    assert "queued_task_has_result" in qa["issues"]

    interrupted=base_row(15,"interrupted")
    interrupted["result"]={"unexpected":True}
    interrupted["lease_until"]=(NOW+timedelta(minutes=1)).isoformat()
    ia=audit_task_row(interrupted,now=NOW)
    assert "interrupted_task_has_result" in ia["issues"]
    assert "interrupted_task_has_live_lease" in ia["issues"]

def test_complete_summary_reports_hashed_findings_only():
    good=base_row(16)
    bad=base_row(17,"running")
    bad["checkpoint"]="starting"
    bad["lease_until"]=(NOW-timedelta(minutes=5)).isoformat()
    report=summarise_task_ledger([good,bad],scan_complete=True,capped=False,now=NOW)
    assert report["version"]==VERSION
    assert report["status"]=="complete_with_ledger_issues"
    assert report["tasks_observed"]==2
    assert report["valid_task_rows"]==1
    assert report["invalid_task_rows"]==1
    assert report["issue_codes"]["running_task_missing_worker"]==1
    assert report["issue_codes"]["running_task_lease_expired"]==1
    finding=report["findings"][0]
    assert len(finding["request_ref"])==12
    assert rid(17) not in str(report)
    assert "private request" not in str(report)
    assert OWNER not in str(report)

def test_complete_healthy_and_capped_states_are_distinct():
    healthy=summarise_task_ledger([base_row(18)],scan_complete=True,capped=False,now=NOW)
    capped=summarise_task_ledger([base_row(18)],scan_complete=False,capped=True,now=NOW)
    assert healthy["status"]=="complete_healthy"
    assert healthy["claims"]["ledger_consistency"]=="verified"
    assert capped["status"]=="incomplete_scan"
    assert capped["scan_complete"] is False
    assert capped["claims"]["ledger_consistency"]=="not_verified"

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

def test_loader_pages_owner_ledger_and_is_strictly_read_only():
    rows=[base_row(100+i) for i in range(7)]
    client=Client(rows)
    report=load_task_ledger_audit(client,TOKEN,page_size=3,max_rows=20)
    assert report["scan_complete"] is True
    assert report["tasks_observed"]==7
    assert report["scan"]["pages_read"]==3
    assert report["scan"]["rows_read"]==7
    assert report["scan"]["read_only"] is True
    assert ("range",0,2) in client.calls and ("range",3,5) in client.calls and ("range",6,8) in client.calls
    assert any(x[0]=="eq" and x[1]=="user_id" for x in client.calls)
    assert any(x[0]=="eq" and x[1]=="owner_hash" for x in client.calls)
    assert not any(x[0] in {"insert","update","delete","upsert","rpc"} for x in client.calls)

def test_loader_cap_never_claims_complete_ledger():
    rows=[base_row(200+i) for i in range(6)]
    report=load_task_ledger_audit(Client(rows),TOKEN,page_size=2,max_rows=4)
    assert report["scan_complete"] is False
    assert report["capped"] is True
    assert report["scan"]["rows_read"]==4
    assert report["claims"]["ledger_consistency"]=="not_verified"

@pytest.mark.parametrize("page,max_rows",[(0,100),(101,100),(1.5,100),(10,0),(10,10001),(10,"100")])
def test_loader_rejects_invalid_bounds(page,max_rows):
    with pytest.raises(ValueError):
        load_task_ledger_audit(Client([]),TOKEN,page_size=page,max_rows=max_rows)

def test_server_endpoint_returns_privacy_safe_ledger_audit(monkeypatch):
    from api import server
    client=Client([base_row(300)])
    monkeypatch.setattr(server.task_store,"client",client)
    report=server.cognition_durable_task_ledger_audit(page_size=50,max_rows=1000,x_l_recovery_token=TOKEN)
    assert report["mode"]=="durable_task_ledger_audit"
    assert report["status"]=="complete_healthy"
    assert report["actions"]["automatic_repair"] is False
    assert report["privacy"]["request_payloads_returned"] is False

def test_server_surfaces_layer111_ledger_readiness():
    from pathlib import Path
    source=Path("api/server.py").read_text(encoding="utf-8")
    assert '"release_layer":' in source
    assert '"durable_task_ledger_audit_ready": True' in source
    assert '@app.get("/cognition/durable-task-ledger-audit")' in source
    assert "load_task_ledger_audit(" in source
