from pathlib import Path

from services.foundation_companion_service import foundation_concierge_jobs_as_user

USER="11111111-1111-4111-8111-111111111111"
REQUEST="22222222-2222-4222-8222-222222222222"

class Response:
    def __init__(self,payload):
        import json
        self.status_code=200; self.payload=payload
        self.content=json.dumps(payload).encode()
        self.headers={"content-length":str(len(self.content))}
    def json(self): return self.payload

def body(seconds=600,state="start-soon",attention=True,action="start-or-retire",contract=None):
    return {
      "status":"ok",
      "privacy":{"conversationTextIncluded":False,"specialistInputIncluded":False,"specialistOutputIncluded":False},
      "planTtlContract":{"version":"shine-foundation/concierge-plan-ttl-v1","ttlSeconds":3600,"computedBy":"foundation-server","clientClockAuthoritative":False,"startedExecutionExempt":True,"expiryDueMutatesState":False},
      "deadlinePostureContract": contract or {"version":"shine-foundation/concierge-deadline-posture-v1","startSoonThresholdSeconds":600,"automaticExecutionTriggered":False,"automaticRetryTriggered":False,"readMutatesState":False,"source":"foundation-server"},
      "summary":{"total":1,"deadlineAttention":1 if attention else 0},
      "items":[{
        "requestId":REQUEST,"clientId":"shine.companion","clientName":"Shine Companion",
        "purpose":"concierge.cross-project-read","requestedAt":"2026-09-28T07:11:00Z",
        "status":"planned","requestedCapabilities":["travel.plan_trip"],
        "progress":{"totalSteps":1,"historicallyCompletedSteps":0},
        "waitingOn":"companion","attentionRequired":False,"attentionReason":"Automatic work",
        "attentionOrder":50,"nextAction":None,"canCancel":True,
        "cancellationReceiptIntegrity":None,"cancellationReceipt":None,
        "retirementReceiptIntegrity":None,"retirementReceipt":None,"supersededByRequestId":None,
        "planTtl":{"applies":True,"state":"counting-down" if seconds else "expiry-due","reasonCode":"concierge-plan-within-ttl" if seconds else "concierge-plan-expiry-due","expiresAt":"2026-09-28T08:01:00Z","secondsRemaining":seconds,"serverTime":"2026-09-28T07:51:00Z"},
        "deadlinePosture":{"state":state,"attentionRequired":attention,"reasonCode":"concierge-plan-near-expiry" if state=="start-soon" else "concierge-plan-expiry-due","action":action,"automaticExecutionTriggered":False}
      }]
    }

def read(payload):
    return foundation_concierge_jobs_as_user(None,USER,authorization="Bearer "+"u"*64,get_impl=lambda *a,**k:Response(payload))

def test_start_soon_posture_is_projected_as_attention_only():
    result=read(body())
    p=result["items"][0]["deadline_posture"]
    assert p["state"]=="start-soon"
    assert p["attention_required"] is True
    assert p["action"]=="start-or-retire"
    assert p["automatic_execution_triggered"] is False
    assert result["deadline_posture_contract"]["automatic_execution_triggered"] is False
    assert result["deadline_posture_contract"]["automatic_retry_triggered"] is False
    assert result["deadline_posture_contract"]["read_mutates_state"] is False

def test_expiry_due_posture_is_projected_without_execution():
    result=read(body(seconds=0,state="expiry-due",attention=True,action="retire-before-execution"))
    p=result["items"][0]["deadline_posture"]
    assert p["state"]=="expiry-due"
    assert p["action"]=="retire-before-execution"
    assert p["automatic_execution_triggered"] is False

def test_invalid_deadline_contract_drops_posture():
    bad={"version":"shine-foundation/concierge-deadline-posture-v1","startSoonThresholdSeconds":600,"automaticExecutionTriggered":True,"automaticRetryTriggered":False,"readMutatesState":False,"source":"foundation-server"}
    result=read(body(contract=bad))
    assert result["deadline_posture_contract"]["valid"] is False
    assert result["items"][0]["deadline_posture"] is None

def test_invalid_deadline_shape_drops_posture():
    result=read(body(state="start-soon",attention=False,action="start-or-retire"))
    assert result["items"][0]["deadline_posture"] is None

def test_ui_gives_deadline_posture_precedence_over_early_urgency():
    bridge=Path("ui/concierge-completions.js").read_text(encoding="utf-8")
    index=Path("ui/index.html").read_text(encoding="utf-8")
    assert "function deadlinePostureText" in bridge
    assert "Start soon · 10 min or less before this unused plan retires." in bridge
    assert "automatic_execution_triggered === false" in bridge
    assert "taskCentreJob.deadlinePostureText" in index
    assert "Plan starts soon or retires" in index
    assert "} else if (" in index[index.index("taskCentreJob.deadlinePostureText"):index.index("const pendingConcierge")]
    assert 'concierge-completions.js?v=197' in index
