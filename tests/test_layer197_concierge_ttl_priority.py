from pathlib import Path

from services.foundation_companion_service import foundation_concierge_jobs_as_user


USER = "11111111-1111-4111-8111-111111111111"
PERMISSION = "22222222-2222-4222-8222-222222222222"
DUE = "33333333-3333-4333-8333-333333333333"


class Response:
    def __init__(self, payload):
        import json

        self.status_code = 200
        self.payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {"content-length": str(len(self.content))}

    def json(self):
        return self.payload


def ttl_contract(**overrides):
    value = {
        "version": "shine-foundation/concierge-plan-ttl-v1",
        "ttlSeconds": 3600,
        "computedBy": "foundation-server",
        "clientClockAuthoritative": False,
        "startedExecutionExempt": True,
        "expiryDueMutatesState": False,
        "warningSeconds": 900,
        "urgencyChangesExecution": False,
        "urgencyAutoStartsWork": False,
    }
    value.update(overrides)
    return value


def base_item(request_id, *, seconds, urgency, priority, order, reason, next_action):
    ttl_state = "expiry-due" if seconds == 0 else "counting-down"
    return {
        "requestId": request_id,
        "clientId": "shine.companion",
        "clientName": "Shine Companion",
        "purpose": "concierge.cross-project-read",
        "requestedAt": "2026-09-28T07:06:00Z",
        "status": "blocked" if request_id == PERMISSION else "planned",
        "requestedCapabilities": ["travel.plan_trip"],
        "progress": {"totalSteps": 1, "historicallyCompletedSteps": 0},
        "waitingOn": "user" if request_id == PERMISSION else "companion",
        "attentionRequired": True,
        "attentionReason": reason,
        "attentionOrder": order,
        "nextAction": next_action,
        "canCancel": True,
        "cancellationReceiptIntegrity": None,
        "cancellationReceipt": None,
        "retirementReceiptIntegrity": None,
        "retirementReceipt": None,
        "supersededByRequestId": None,
        "planTtl": {
            "applies": True,
            "state": ttl_state,
            "reasonCode": (
                "concierge-plan-expiry-due"
                if seconds == 0
                else "concierge-plan-within-ttl"
            ),
            "expiresAt": "2026-09-28T08:06:00Z",
            "secondsRemaining": seconds,
            "serverTime": "2026-09-28T08:01:00Z",
        },
        "planUrgency": {
            "state": urgency,
            "priority": priority,
            "reasonCode": (
                "concierge-plan-expiry-due"
                if urgency == "expiry-due"
                else "concierge-plan-expires-soon"
            ),
            "warningThresholdSeconds": 900,
            "secondsRemaining": seconds,
            "requiresUserAttention": True,
            "autoStartsExecution": False,
        },
    }


def payload(*, contract=None, items=None):
    return {
        "status": "ok",
        "privacy": {
            "conversationTextIncluded": False,
            "specialistInputIncluded": False,
            "specialistOutputIncluded": False,
        },
        "planTtlContract": contract or ttl_contract(),
        "summary": {
            "total": 2,
            "attentionRequired": 2,
            "automatic": 0,
            "expiringSoon": 1,
            "expiryDue": 1,
        },
        "ordering": {
            "deterministic": True,
            "aiPriorityScoreUsed": False,
            "ttlUrgencyUsed": True,
            "ttlUrgencyWarningSeconds": 900,
        },
        "items": items or [
            base_item(
                PERMISSION,
                seconds=300,
                urgency="expiring-soon",
                priority="high",
                order=20,
                reason="Permission required",
                next_action="review-consent",
            ),
            base_item(
                DUE,
                seconds=0,
                urgency="expiry-due",
                priority="critical",
                order=25,
                reason="Plan expired — send a fresh request",
                next_action="send-fresh-request",
            ),
        ],
    }


def read(body):
    return foundation_concierge_jobs_as_user(
        None,
        USER,
        authorization="Bearer " + "u" * 64,
        get_impl=lambda *args, **kwargs: Response(body),
    )


def test_permission_reason_stays_primary_while_ttl_urgency_is_secondary():
    result = read(payload())
    item = result["items"][0]

    assert item["request_id"] == PERMISSION
    assert item["attention_required"] is True
    assert item["attention_reason"] == "Permission required"
    assert item["attention_order"] == 20
    assert item["next_action"] == "review-consent"
    assert item["plan_urgency"] == {
        "version": "1.0",
        "state": "expiring-soon",
        "priority": "high",
        "reason_code": "concierge-plan-expires-soon",
        "warning_threshold_seconds": 900,
        "seconds_remaining": 300,
        "requires_user_attention": True,
        "auto_starts_execution": False,
    }


def test_expiry_due_priority_is_projected_without_execution_authority():
    item = read(payload())["items"][1]
    assert item["request_id"] == DUE
    assert item["attention_order"] == 25
    assert item["attention_reason"] == "Plan expired — send a fresh request"
    assert item["next_action"] == "send-fresh-request"
    assert item["plan_urgency"]["state"] == "expiry-due"
    assert item["plan_urgency"]["priority"] == "critical"
    assert item["plan_urgency"]["auto_starts_execution"] is False


def test_urgency_contract_that_changes_execution_is_rejected():
    result = read(payload(contract=ttl_contract(urgencyChangesExecution=True)))
    assert result["plan_ttl_contract"]["valid"] is True
    assert result["plan_ttl_contract"]["urgency_valid"] is False
    assert result["items"][0]["plan_ttl"] is not None
    assert result["items"][0]["plan_urgency"] is None


def test_urgency_seconds_must_match_server_ttl_seconds():
    bad = base_item(
        PERMISSION,
        seconds=300,
        urgency="expiring-soon",
        priority="high",
        order=20,
        reason="Permission required",
        next_action="review-consent",
    )
    bad["planUrgency"]["secondsRemaining"] = 600

    result = read(payload(items=[bad]))
    assert result["items"][0]["plan_ttl"]["seconds_remaining"] == 300
    assert result["items"][0]["plan_urgency"] is None


def test_saved_answers_orders_attention_before_newest_and_never_auto_executes():
    bridge = Path("ui/concierge-completions.js").read_text(encoding="utf-8")
    index = Path("ui/index.html").read_text(encoding="utf-8")

    assert "function planUrgencyText" in bridge
    assert "Priority notice · this untouched plan is inside its final 15 minutes." in bridge
    assert "Use the question again to create a fresh request" in bridge
    assert "urgency.auto_starts_execution !== false" in bridge

    assert "Needs attention first; then newest." in index
    assert "leftAttention !== rightAttention" in index
    assert "left.job.attentionOrder" in index
    assert "right.job.attentionOrder" in index
    assert "taskCentreJob.attentionReason" in index
    assert "taskCentreJob.planUrgencyText" in index
    assert 'concierge-completions.js?v=197' in index
