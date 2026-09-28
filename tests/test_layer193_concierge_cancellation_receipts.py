from pathlib import Path

import pytest

from services.foundation_companion_service import foundation_concierge_jobs_as_user


USER = "11111111-1111-4111-8111-111111111111"
REQUEST = "22222222-2222-4222-8222-222222222222"
NEW = "33333333-3333-4333-8333-333333333333"


class Response:
    def __init__(self, code, payload):
        import json

        self.status_code = code
        self.payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {"content-length": str(len(self.content))}

    def json(self):
        return self.payload


def receipt(integrity="verified"):
    return {
        "cancellationReceipt": "shine-foundation/concierge-cancellation-receipt-v1",
        "schemaVersion": "1.0.0",
        "requestId": REQUEST,
        "clientId": "shine.companion",
        "reasonCode": "superseded-by-newer-request",
        "cancelledAt": "2026-09-28T04:50:00Z",
        "supersededByRequestId": NEW,
        "progress": {
            "totalSteps": 2,
            "completedBeforeCancellation": 1,
            "pendingAtCancellation": 1,
        },
        "completedCapabilities": ["travel.plan_trip"],
        "pendingCapabilities": ["dive.destination_brief"],
        "steps": [
            {
                "stepId": "44444444-4444-4444-8444-444444444444",
                "capabilityId": "travel.plan_trip",
                "appId": "shine.travel",
                "completedBeforeCancellation": True,
                "completedAt": "2026-09-28T04:49:00Z",
            },
            {
                "stepId": "55555555-5555-4555-8555-555555555555",
                "capabilityId": "dive.destination_brief",
                "appId": "shine.dive",
                "completedBeforeCancellation": False,
                "completedAt": None,
            },
        ],
        "receiptSha256": "a" * 64,
        "integrity": integrity,
    }


def jobs_payload(*, receipt_integrity="verified", privacy=None):
    return {
        "integrationResponse": "shine-foundation/user-concierge-jobs-response-v1",
        "schemaVersion": "1.0.0",
        "status": "ok",
        "reasonCode": "concierge-jobs-listed",
        "privacy": privacy or {
            "conversationTextIncluded": False,
            "specialistInputIncluded": False,
            "specialistOutputIncluded": False,
        },
        "summary": {
            "total": 1,
            "cancelled": 1,
            "superseded": 1,
        },
        "ordering": {"deterministic": True},
        "receiptContract": {
            "version": "shine-foundation/concierge-cancellation-receipt-v1",
            "specialistOutputIncluded": False,
            "conversationTextIncluded": False,
            "tamperEvidentSha256": True,
            "readTimeVerification": True,
        },
        "items": [{
            "requestId": REQUEST,
            "clientId": "shine.companion",
            "clientName": "Shine Companion",
            "purpose": "concierge.cross-project-read",
            "requestedAt": "2026-09-28T04:48:00Z",
            "status": "cancelled",
            "requestedCapabilities": [
                "travel.plan_trip",
                "dive.destination_brief",
            ],
            "progress": {
                "totalSteps": 2,
                "reusableCompletedSteps": 1,
                "historicallyCompletedSteps": 1,
            },
            "waitingOn": "none",
            "attentionRequired": False,
            "attentionReason": "Cancelled",
            "nextAction": None,
            "canCancel": False,
            "supersededByRequestId": NEW,
            "cancellationReceiptIntegrity": receipt_integrity,
            "cancellationReceipt": (
                receipt(receipt_integrity)
                if receipt_integrity == "verified"
                else None
            ),
        }],
    }


def test_task_centre_projects_verified_receipt_without_private_payloads():
    seen = []

    def get(url, *, headers, **kwargs):
        seen.append((url, headers))
        return Response(200, jobs_payload())

    result = foundation_concierge_jobs_as_user(
        None,
        USER,
        authorization="Bearer " + "u" * 64,
        limit=50,
        get_impl=get,
    )

    assert result["status"] == "ok"
    assert result["privacy"] == {
        "conversation_text_included": False,
        "specialist_input_included": False,
        "specialist_output_included": False,
    }
    assert result["rejected_receipt_count"] == 0
    item = result["items"][0]
    assert item["request_id"] == REQUEST
    assert item["status"] == "cancelled"
    assert item["superseded_by_request_id"] == NEW
    assert item["cancellation_receipt_integrity"] == "verified"

    safe = item["cancellation_receipt"]
    assert safe["integrity"] == "verified"
    assert safe["reason_code"] == "superseded-by-newer-request"
    assert safe["progress"] == {
        "total_steps": 2,
        "completed_before_cancellation": 1,
        "pending_at_cancellation": 1,
    }
    assert safe["completed_capabilities"] == ["travel.plan_trip"]
    assert safe["pending_capabilities"] == ["dive.destination_brief"]
    assert all("result" not in step for step in safe["steps"])
    assert "input" not in repr(item).lower()
    assert seen[0][1]["Authorization"].startswith("Bearer ")


def test_task_centre_rejects_unverified_receipt_without_reconstructing_it():
    def get(*args, **kwargs):
        return Response(200, jobs_payload(receipt_integrity="mismatch"))

    result = foundation_concierge_jobs_as_user(
        None,
        USER,
        authorization="Bearer " + "u" * 64,
        get_impl=get,
    )

    assert result["items"][0]["cancellation_receipt"] is None
    assert result["items"][0]["cancellation_receipt_integrity"] == "mismatch"
    assert result["rejected_receipt_count"] == 0


def test_task_centre_fails_closed_if_foundation_privacy_contract_widens():
    def get(*args, **kwargs):
        return Response(200, jobs_payload(privacy={
            "conversationTextIncluded": True,
            "specialistInputIncluded": False,
            "specialistOutputIncluded": False,
        }))

    with pytest.raises(RuntimeError, match="privacy-contract-invalid"):
        foundation_concierge_jobs_as_user(
            None,
            USER,
            authorization="Bearer " + "u" * 64,
            get_impl=get,
        )


def test_owner_api_exposes_task_centre_history():
    source = Path("api/foundation_companion.py").read_text(encoding="utf-8")
    assert '@router.get("/jobs")' in source
    assert "foundation_concierge_jobs_as_user" in source
    assert 'authorization=request.headers.get("authorization", "")' in source


def test_saved_answers_explains_verified_cancellation_without_rewriting_answer():
    bridge = Path("ui/concierge-completions.js").read_text(encoding="utf-8")
    index = Path("ui/index.html").read_text(encoding="utf-8")

    assert "function cancellationReceiptText" in bridge
    assert "async function taskCentre" in bridge
    assert "completed before cancellation" in bridge
    assert "Still pending at cancellation" in bridge
    assert "Verified receipt SHA-256" in bridge
    assert "jobs: (limit = 50) => taskCentre(limit)" in bridge

    assert "conciergeJobs: new Map()" in index
    assert "window.lConciergeCompletions?.jobs?.(50)" in index
    assert "Concierge history — " in index
    assert "Saved answer · delayed work superseded" in index
    assert "Saved answer · delayed work cancelled" in index
    assert "Cancellation receipt verification failed" in index
    assert "savedText += '\\n\\n' + taskCentreJob.cancellationText" in index
    assert 'concierge-completions.js?v=195' in index
