from pathlib import Path

from services.foundation_companion_service import foundation_concierge_jobs_as_user


USER = "11111111-1111-4111-8111-111111111111"
REQUEST = "22222222-2222-4222-8222-222222222222"


class Response:
    def __init__(self, code, payload):
        import json

        self.status_code = code
        self.payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {"content-length": str(len(self.content))}

    def json(self):
        return self.payload


def retired_payload(*, integrity="verified"):
    receipt = {
        "retirementReceipt": "shine-foundation/concierge-retirement-receipt-v1",
        "schemaVersion": "1.0.0",
        "requestId": REQUEST,
        "clientId": "shine.companion",
        "reasonCode": "unused-plan-expired",
        "requestedAt": "2026-09-27T12:00:00Z",
        "retiredAt": "2026-09-28T05:00:00Z",
        "minimumAgeSeconds": 3600,
        "requestedCapabilities": ["travel.plan_trip"],
        "stepCount": 1,
        "executionStarted": False,
        "specialistCheckpointCount": 0,
        "retryCount": 0,
        "receiptSha256": "a" * 64,
        "integrity": integrity,
    }
    return {
        "integrationResponse": "shine-foundation/user-concierge-jobs-response-v1",
        "schemaVersion": "1.0.0",
        "status": "ok",
        "reasonCode": "concierge-jobs-listed",
        "privacy": {
            "conversationTextIncluded": False,
            "specialistInputIncluded": False,
            "specialistOutputIncluded": False,
        },
        "summary": {
            "total": 1,
            "retired": 1,
        },
        "items": [{
            "requestId": REQUEST,
            "clientId": "shine.companion",
            "clientName": "Shine Companion",
            "purpose": "concierge.cross-project-read",
            "requestedAt": "2026-09-27T12:00:00Z",
            "status": "retired",
            "requestedCapabilities": ["travel.plan_trip"],
            "progress": {
                "totalSteps": 1,
                "historicallyCompletedSteps": 0,
            },
            "waitingOn": "none",
            "attentionRequired": False,
            "attentionReason": "Expired unused",
            "nextAction": None,
            "canCancel": False,
            "retirementReceiptIntegrity": integrity,
            "retirementReceipt": receipt if integrity == "verified" else None,
            "cancellationReceiptIntegrity": None,
            "cancellationReceipt": None,
            "supersededByRequestId": None,
        }],
    }


def test_task_centre_projects_verified_retirement_receipt():
    def get(*args, **kwargs):
        return Response(200, retired_payload())

    result = foundation_concierge_jobs_as_user(
        None,
        USER,
        authorization="Bearer " + "u" * 64,
        get_impl=get,
    )

    assert result["status"] == "ok"
    item = result["items"][0]
    assert item["status"] == "retired"
    assert item["can_cancel"] is False
    assert item["retirement_receipt_integrity"] == "verified"
    receipt = item["retirement_receipt"]
    assert receipt == {
        "version": "1.0",
        "request_id": REQUEST,
        "reason_code": "unused-plan-expired",
        "requested_at": "2026-09-27T12:00:00Z",
        "retired_at": "2026-09-28T05:00:00Z",
        "minimum_age_seconds": 3600,
        "requested_capabilities": ["travel.plan_trip"],
        "step_count": 1,
        "execution_started": False,
        "specialist_checkpoint_count": 0,
        "retry_count": 0,
        "receipt_sha256": "a" * 64,
        "integrity": "verified",
    }


def test_task_centre_does_not_reconstruct_bad_retirement_receipt():
    def get(*args, **kwargs):
        return Response(200, retired_payload(integrity="mismatch"))

    result = foundation_concierge_jobs_as_user(
        None,
        USER,
        authorization="Bearer " + "u" * 64,
        get_impl=get,
    )
    item = result["items"][0]
    assert item["status"] == "retired"
    assert item["retirement_receipt"] is None
    assert item["retirement_receipt_integrity"] == "mismatch"


def test_retirement_ui_explains_expiry_without_calling_it_failure_or_cancel():
    bridge = Path("ui/concierge-completions.js").read_text(encoding="utf-8")
    index = Path("ui/index.html").read_text(encoding="utf-8")

    assert "function retirementReceiptText" in bridge
    assert "this Concierge plan expired unused" in bridge
    assert "Execution never started." in bridge
    assert "no specialist checkpoint was written and no retry was queued" in bridge.lower()
    assert "retirementReceiptIntegrity" in bridge
    assert "retirementText" in bridge

    assert "['cancelled', 'retired'].includes(item.status)" in index
    assert "Retired Concierge plan" in index
    assert "Saved answer · delayed plan expired unused" in index
    assert "Retirement receipt verification failed" in index
    assert 'concierge-completions.js?v=195' in index


def test_retired_history_never_exposes_cancel_control():
    index = Path("ui/index.html").read_text(encoding="utf-8")
    retired_case = index.index("taskCentreJob?.status === 'retired'")
    cancel_case = index.index("taskCentreJob?.status === 'cancelled'", retired_case)
    window = index[retired_case:cancel_case]
    assert "Cancel delayed work" not in window



class RpcResult:
    def __init__(self, data):
        self.data = data


class RpcCall:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return RpcResult(self.data)


class ReconcileDb:
    def __init__(self):
        self.calls = []

    def rpc(self, name, params=None):
        self.calls.append((name, params or {}))
        if name == "companion_mark_local_concierge_retired_v1":
            return RpcCall({
                "status": "retired",
                "requestId": REQUEST,
            })
        raise AssertionError(name)


def test_verified_foundation_retirement_reconciles_local_pending_snapshot():
    db = ReconcileDb()

    def get(*args, **kwargs):
        return Response(200, retired_payload())

    result = foundation_concierge_jobs_as_user(
        db,
        USER,
        authorization="Bearer " + "u" * 64,
        get_impl=get,
    )

    assert result["items"][0]["local_retirement_reconciliation"] == "retired"
    name, params = db.calls[0]
    assert name == "companion_mark_local_concierge_retired_v1"
    assert params["p_request_id"] == REQUEST
    assert params["p_reason_code"] == "unused-plan-expired"
    assert params["p_receipt_sha256"] == "a" * 64


def test_terminal_task_centre_status_clears_pending_overlay():
    index = Path("ui/index.html").read_text(encoding="utf-8")
    assert "['cancelled', 'retired', 'completed', 'failed'].includes(item.status)" in index
    assert "run.pendingConcierge.delete(item.requestId)" in index
