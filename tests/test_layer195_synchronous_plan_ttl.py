from pathlib import Path

from services.concierge_execution_service import bind_concierge_execution
from services.foundation_companion_service import _safe_foundation_retirement


REQUEST = "11111111-1111-4111-8111-111111111111"


def retirement_payload():
    return {
        "status": "retired",
        "reasonCode": "unused-plan-expired",
        "requestId": REQUEST,
        "retiredAt": "2026-09-28T06:07:00Z",
        "receiptSha256": "a" * 64,
        "receipt": {
            "retirementReceipt": "shine-foundation/concierge-retirement-receipt-v1",
            "schemaVersion": "1.0.0",
            "requestId": REQUEST,
            "clientId": "shine.companion",
            "reasonCode": "unused-plan-expired",
            "requestedAt": "2026-09-28T05:06:59Z",
            "retiredAt": "2026-09-28T06:07:00Z",
            "minimumAgeSeconds": 3600,
            "requestedCapabilities": ["travel.plan_trip"],
            "stepCount": 1,
            "executionStarted": False,
            "specialistCheckpointCount": 0,
            "retryCount": 0,
        },
    }


def test_foundation_retirement_receipt_is_projected_only_when_ttl_contract_is_valid():
    result = _safe_foundation_retirement(retirement_payload(), REQUEST)

    assert result == {
        "version": "1.0",
        "status": "retired",
        "request_id": REQUEST,
        "reason_code": "unused-plan-expired",
        "requested_at": "2026-09-28T05:06:59Z",
        "retired_at": "2026-09-28T06:07:00Z",
        "minimum_age_seconds": 3600,
        "requested_capabilities": ["travel.plan_trip"],
        "step_count": 1,
        "execution_started": False,
        "specialist_checkpoint_count": 0,
        "retry_count": 0,
        "receipt_sha256": "a" * 64,
        "integrity": "foundation-live",
    }


def test_retirement_receipt_rejects_any_claim_that_specialist_work_already_happened():
    payload = retirement_payload()
    payload["receipt"]["specialistCheckpointCount"] = 1
    assert _safe_foundation_retirement(payload, REQUEST) is None

    payload = retirement_payload()
    payload["receipt"]["executionStarted"] = True
    assert _safe_foundation_retirement(payload, REQUEST) is None


def test_retired_execution_never_becomes_synthesis_evidence():
    route = {
        "capability": "foundation_specialist",
        "status": "ready",
        "handled": False,
        "reply": "",
    }
    execution = {
        "status": "retired",
        "reason_code": "concierge-plan-expired",
        "foundation_status": "blocked",
        "foundation_reason_code": "concierge-plan-expired",
        "selected_capabilities": ["travel.plan_trip"],
        "executed_capabilities": [],
        "completed_capabilities": [],
        "unavailable_capabilities": ["travel.plan_trip"],
        "skipped_capabilities": [],
        "execution_performed": False,
        "retirement": {
            "version": "1.0",
            "request_id": REQUEST,
            "reason_code": "unused-plan-expired",
        },
        "synthesis_ready": False,
        "synthesis_must_disclose_partial": False,
        "results": [],
    }

    bound = bind_concierge_execution(route, execution)

    assert bound["status"] == "retired"
    assert bound["handled"] is False
    assert bound["reply"] == ""
    assert bound["foundation_execution"]["synthesis_ready"] is False
    assert bound["foundation_execution"]["retirement"]["reason_code"] == "unused-plan-expired"


def test_project_l_maps_foundation_expiry_block_to_retired_before_local_failure_logic():
    foundation = Path("services/foundation_companion_service.py").read_text(encoding="utf-8")
    execution = Path("services/concierge_execution_service.py").read_text(encoding="utf-8")

    assert '"concierge-plan-expired"' in foundation
    assert '"concierge-request-retired"' in foundation
    assert '"status": "retired" if expiry_block else foundation_status' in foundation
    assert "concierge-retirement-receipt-invalid" in foundation

    retired_index = execution.index('if status == "retired":')
    failed_index = execution.index('elif status in {"blocked", "denied", "failed", "invalid"}:')
    assert retired_index < failed_index
    assert "mark_local_concierge_retired" in execution[retired_index:failed_index]
