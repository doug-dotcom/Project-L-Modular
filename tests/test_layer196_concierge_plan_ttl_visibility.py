from pathlib import Path

from services.foundation_companion_service import foundation_concierge_jobs_as_user


USER = "11111111-1111-4111-8111-111111111111"
REQUEST = "22222222-2222-4222-8222-222222222222"


class Response:
    def __init__(self, payload):
        import json
        self.status_code = 200
        self.payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {"content-length": str(len(self.content))}
    def json(self):
        return self.payload


def payload(*, ttl_contract=None, plan_ttl=None):
    contract = ttl_contract if ttl_contract is not None else {
        "version": "shine-foundation/concierge-plan-ttl-v1",
        "ttlSeconds": 3600,
        "computedBy": "foundation-server",
        "clientClockAuthoritative": False,
        "startedExecutionExempt": True,
        "expiryDueMutatesState": False,
    }
    ttl = plan_ttl if plan_ttl is not None else {
        "applies": True,
        "state": "counting-down",
        "reasonCode": "concierge-plan-within-ttl",
        "expiresAt": "2026-09-28T08:31:00Z",
        "secondsRemaining": 1800,
        "serverTime": "2026-09-28T08:01:00Z",
    }
    return {
        "status": "ok",
        "privacy": {
            "conversationTextIncluded": False,
            "specialistInputIncluded": False,
            "specialistOutputIncluded": False,
        },
        "planTtlContract": contract,
        "summary": {"total": 1},
        "items": [{
            "requestId": REQUEST,
            "clientId": "shine.companion",
            "clientName": "Shine Companion",
            "purpose": "concierge.cross-project-read",
            "requestedAt": "2026-09-28T07:31:00Z",
            "status": "planned",
            "requestedCapabilities": ["travel.plan_trip"],
            "progress": {"totalSteps": 1, "historicallyCompletedSteps": 0},
            "waitingOn": "companion",
            "attentionRequired": False,
            "attentionReason": "Automatic work",
            "nextAction": None,
            "canCancel": True,
            "cancellationReceiptIntegrity": None,
            "cancellationReceipt": None,
            "retirementReceiptIntegrity": None,
            "retirementReceipt": None,
            "supersededByRequestId": None,
            "planTtl": ttl,
        }],
    }


def read(body):
    return foundation_concierge_jobs_as_user(
        None,
        USER,
        authorization="Bearer " + "u" * 64,
        get_impl=lambda *args, **kwargs: Response(body),
    )


def test_server_authoritative_countdown_is_projected_without_recalculation():
    result = read(payload())
    assert result["plan_ttl_contract"] == {
        "version": "shine-foundation/concierge-plan-ttl-v1",
        "ttl_seconds": 3600,
        "server_authoritative": True,
        "client_clock_authoritative": False,
        "valid": True,
    }
    ttl = result["items"][0]["plan_ttl"]
    assert ttl == {
        "version": "1.0",
        "state": "counting-down",
        "applies": True,
        "reason_code": "concierge-plan-within-ttl",
        "expires_at": "2026-09-28T08:31:00Z",
        "seconds_remaining": 1800,
        "server_time": "2026-09-28T08:01:00Z",
        "server_authoritative": True,
    }


def test_expiry_due_is_zero_seconds_but_does_not_mutate_state():
    body = payload(plan_ttl={
        "applies": True,
        "state": "expiry-due",
        "reasonCode": "concierge-plan-expiry-due",
        "expiresAt": "2026-09-28T08:00:00Z",
        "secondsRemaining": 0,
        "serverTime": "2026-09-28T08:01:00Z",
    })
    result = read(body)
    ttl = result["items"][0]["plan_ttl"]
    assert ttl["state"] == "expiry-due"
    assert ttl["seconds_remaining"] == 0
    assert result["items"][0]["status"] == "planned"


def test_started_exempt_has_no_fake_deadline():
    body = payload(plan_ttl={
        "applies": False,
        "state": "started-exempt",
        "reasonCode": "concierge-execution-already-started",
        "expiresAt": None,
        "secondsRemaining": None,
        "serverTime": "2026-09-28T08:01:00Z",
    })
    ttl = read(body)["items"][0]["plan_ttl"]
    assert ttl["state"] == "started-exempt"
    assert ttl["expires_at"] is None
    assert ttl["seconds_remaining"] is None


def test_bad_foundation_ttl_contract_drops_countdown_instead_of_guessing():
    body = payload(ttl_contract={
        "version": "shine-foundation/concierge-plan-ttl-v1",
        "ttlSeconds": 7200,
        "computedBy": "browser",
        "clientClockAuthoritative": True,
        "startedExecutionExempt": True,
        "expiryDueMutatesState": False,
    })
    result = read(body)
    assert result["plan_ttl_contract"]["valid"] is False
    assert result["items"][0]["plan_ttl"] is None


def test_invalid_countdown_shape_is_dropped():
    body = payload(plan_ttl={
        "applies": True,
        "state": "counting-down",
        "reasonCode": "concierge-plan-within-ttl",
        "expiresAt": "2026-09-28T08:31:00Z",
        "secondsRemaining": -5,
        "serverTime": "2026-09-28T08:01:00Z",
    })
    assert read(body)["items"][0]["plan_ttl"] is None


def test_ui_formats_ttl_states_without_using_browser_clock_as_authority():
    bridge = Path("ui/concierge-completions.js").read_text(encoding="utf-8")
    index = Path("ui/index.html").read_text(encoding="utf-8")

    assert "function planTtlText" in bridge
    assert "Waiting to execute · expires in " in bridge
    assert "Expiry due · Foundation will retire this unused plan before execution." in bridge
    assert "Execution started · the one-hour plan deadline no longer applies." in bridge
    assert "ttl.seconds_remaining" in bridge
    assert "new Date(ttl.expires_at)" in bridge
    assert "Date.now()" not in bridge[bridge.index("function planTtlText"):bridge.index("async function taskCentre")]
    assert "taskCentreJob.planTtlText" in index
    assert "Plan expiry due" in index
    assert 'src="/ui/concierge-completions.js?v=' in index
