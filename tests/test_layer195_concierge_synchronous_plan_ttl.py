import json

from services.concierge_execution_service import execute_concierge_route
from services.foundation_companion_service import (
    _safe_foundation_retirement,
    cancel_foundation_concierge_request_as_user,
)


USER = "11111111-1111-4111-8111-111111111111"
REQUEST = "22222222-2222-4222-8222-222222222222"
LINK = "33333333-3333-4333-8333-333333333333"


class Result:
    def __init__(self, data):
        self.data = data


class Rpc:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return Result(self.data)


class Query:
    def __init__(self, db, table, mode="select", payload=None):
        self.db = db
        self.table_name = table
        self.mode = mode
        self.payload = payload
        self.filters = {}
        self.limit_value = None

    def select(self, *args):
        return self

    def eq(self, key, value):
        self.filters[("eq", key)] = value
        return self

    def neq(self, key, value):
        self.filters[("neq", key)] = value
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def insert(self, payload):
        return Query(self.db, self.table_name, "insert", payload)

    def update(self, payload):
        return Query(self.db, self.table_name, "update", payload)

    def _matches(self, row):
        for (op, key), value in self.filters.items():
            if op == "eq" and str(row.get(key)) != str(value):
                return False
            if op == "neq" and str(row.get(key)) == str(value):
                return False
        return True

    def execute(self):
        rows = self.db.tables.setdefault(self.table_name, [])
        if self.mode == "select":
            selected = [dict(row) for row in rows if self._matches(row)]
            if self.limit_value is not None:
                selected = selected[: self.limit_value]
            return Result(selected)
        if self.mode == "insert":
            rows.append(dict(self.payload))
            return Result([dict(self.payload)])
        if self.mode == "update":
            changed = []
            for row in rows:
                if self._matches(row):
                    row.update(self.payload)
                    changed.append(dict(row))
            return Result(changed)
        raise AssertionError(self.mode)


class FakeDb:
    def __init__(self):
        self.tables = {"companion_foundation_pending_jobs": []}

    def table(self, name):
        return Query(self, name)

    def rpc(self, name, params=None):
        params = params or {}
        if name == "companion_claim_foundation_refresh_v2":
            return Rpc({
                "state": "active",
                "requestId": LINK,
                "delegationExpiresAt": "2026-09-29T00:00:00Z",
                "refreshExpiresAt": "2026-10-29T00:00:00Z",
                "refreshGeneration": 1,
            })
        if name == "companion_foundation_delegation_token_v1":
            return Rpc("d" * 128)
        if name == "concierge_foundation_client_token_v1":
            return Rpc("c" * 128)
        if name == "companion_mark_local_concierge_retired_v1":
            for row in self.tables["companion_foundation_pending_jobs"]:
                if (
                    row.get("job_id") == params["p_request_id"]
                    and row.get("user_id") == params["p_user_id"]
                ):
                    row["status"] = "retired"
                    row["retirement_reason"] = params["p_reason_code"]
                    row["retired_at"] = params["p_retired_at"]
                    row["retirement_receipt_sha256"] = params["p_receipt_sha256"]
                    return Rpc({
                        "status": "retired",
                        "requestId": params["p_request_id"],
                    })
            return Rpc({"status": "not-found"})
        if name == "companion_begin_local_concierge_cancel_v1":
            for row in self.tables["companion_foundation_pending_jobs"]:
                if row.get("job_id") == params["p_request_id"]:
                    if row.get("status") == "retired":
                        return Rpc({
                            "status": "retired",
                            "requestId": params["p_request_id"],
                            "reasonCode": row.get("retirement_reason"),
                            "retiredAt": row.get("retired_at"),
                            "receiptSha256": row.get("retirement_receipt_sha256"),
                        })
            return Rpc({"status": "not-found", "requestId": params["p_request_id"]})
        raise AssertionError(name)


class Response:
    def __init__(self, code, payload):
        self.status_code = code
        self.payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {"content-length": str(len(self.content))}

    def json(self):
        return self.payload


def retirement(status="retired"):
    return {
        "status": status,
        "reasonCode": "unused-plan-expired",
        "requestId": REQUEST,
        "retiredAt": "2026-09-28T06:00:00Z",
        "receiptSha256": "a" * 64,
        "receipt": {
            "retirementReceipt": "shine-foundation/concierge-retirement-receipt-v1",
            "schemaVersion": "1.0.0",
            "requestId": REQUEST,
            "clientId": "shine.companion",
            "reasonCode": "unused-plan-expired",
            "requestedAt": "2026-09-28T04:59:00Z",
            "retiredAt": "2026-09-28T06:00:00Z",
            "minimumAgeSeconds": 3600,
            "requestedCapabilities": ["travel.plan_trip"],
            "stepCount": 1,
            "executionStarted": False,
            "specialistCheckpointCount": 0,
            "retryCount": 0,
        },
    }


def route():
    return {
        "handled": False,
        "capability": "foundation_specialist",
        "status": "ready",
        "reply": "",
        "foundation_specialist": {
            "capability_id": "travel.plan_trip",
            "app_name": "Shine Travel",
            "display_name": "Plan a trip",
            "executable": True,
            "runtime_available": True,
            "reason_code": "capability-ready",
            "input_contract": {
                "status": "ready",
                "input_data": {"destination": "Vanuatu"},
            },
        },
    }


def test_expired_gate_projects_retired_and_reconciles_local_state():
    db = FakeDb()
    seen = []

    def post(url, *, json, **kwargs):
        seen.append(url)
        if url.endswith("/v1/concierge/plan"):
            return Response(200, {
                "status": "planned",
                "reasonCode": "concierge-plan-created",
            })
        if url.endswith("/v1/concierge/execute"):
            return Response(409, {
                "status": "blocked",
                "reasonCode": "concierge-plan-expired",
                "gate": {
                    "status": "blocked",
                    "reasonCode": "concierge-plan-expired",
                    "retirement": retirement(),
                },
            })
        raise AssertionError(url)

    result = execute_concierge_route(
        db,
        USER,
        request_id=REQUEST,
        route=route(),
        post_impl=post,
        source_conversation_id="44444444-4444-4444-8444-444444444444",
        source_message_id=REQUEST,
        request_text="Plan Vanuatu",
    )

    assert result["status"] == "retired"
    assert result["reason_code"] == "concierge-plan-expired"
    assert result["execution_performed"] is False
    assert result["local_retry_state"] == "retired"
    assert result["retirement"]["receipt_sha256"] == "a" * 64
    row = db.tables["companion_foundation_pending_jobs"][0]
    assert row["status"] == "retired"
    assert row["retirement_reason"] == "unused-plan-expired"
    assert row["retirement_receipt_sha256"] == "a" * 64
    assert not any("supersede" in url for url in seen)


def test_malformed_expiry_receipt_fails_closed_and_does_not_retire_local_job():
    db = FakeDb()
    malformed = retirement()
    malformed["receiptSha256"] = "bad"

    def post(url, *, json, **kwargs):
        if url.endswith("/v1/concierge/plan"):
            return Response(200, {"status": "planned"})
        if url.endswith("/v1/concierge/execute"):
            return Response(409, {
                "status": "blocked",
                "reasonCode": "concierge-plan-expired",
                "gate": {
                    "status": "blocked",
                    "reasonCode": "concierge-plan-expired",
                    "retirement": malformed,
                },
            })
        raise AssertionError(url)

    result = execute_concierge_route(
        db,
        USER,
        request_id=REQUEST,
        route=route(),
        post_impl=post,
        source_conversation_id="44444444-4444-4444-8444-444444444444",
        source_message_id=REQUEST,
        request_text="Plan Vanuatu",
    )

    assert result["status"] == "unavailable"
    assert result["reason_code"] == "concierge-retirement-receipt-invalid"
    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "ready"


def test_retirement_validator_rejects_started_or_subhour_receipts():
    started = retirement()
    started["receipt"]["executionStarted"] = True
    assert _safe_foundation_retirement(started, REQUEST) is None

    too_young = retirement()
    too_young["receipt"]["minimumAgeSeconds"] = 3599
    assert _safe_foundation_retirement(too_young, REQUEST) is None

    checkpointed = retirement()
    checkpointed["receipt"]["specialistCheckpointCount"] = 1
    assert _safe_foundation_retirement(checkpointed, REQUEST) is None


def test_cancel_short_circuits_when_local_job_is_already_retired():
    db = FakeDb()
    db.tables["companion_foundation_pending_jobs"].append({
        "job_id": REQUEST,
        "user_id": USER,
        "status": "retired",
        "retirement_reason": "unused-plan-expired",
        "retired_at": "2026-09-28T06:00:00Z",
        "retirement_receipt_sha256": "a" * 64,
    })

    result = cancel_foundation_concierge_request_as_user(
        db,
        USER,
        request_id=REQUEST,
        authorization="Bearer " + "u" * 64,
        post_impl=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("retired local job must not call Foundation")
        ),
    )

    assert result["status"] == "retired"
    assert result["reason_code"] == "unused-plan-expired"
    assert result["receipt_sha256"] == "a" * 64


def test_layer195_source_contracts_are_present():
    from pathlib import Path

    foundation_service = Path(
        "services/foundation_companion_service.py"
    ).read_text(encoding="utf-8")
    execution_service = Path(
        "services/concierge_execution_service.py"
    ).read_text(encoding="utf-8")

    assert "concierge-plan-expired" in foundation_service
    assert "concierge-request-retired" in foundation_service
    assert "def _safe_foundation_retirement(" in foundation_service
    assert "def mark_local_concierge_retired(" in foundation_service
    assert '"status": "retired" if expiry_block else foundation_status' in foundation_service
    assert "mark_local_concierge_retired" in execution_service



def test_cancel_ui_accepts_retired_terminal_outcome():
    from pathlib import Path

    bridge = Path("ui/concierge-completions.js").read_text(encoding="utf-8")
    index = Path("ui/index.html").read_text(encoding="utf-8")

    cancel_block = bridge[
        bridge.index("async function cancelPending"):
        bridge.index("function cancellationReceiptText")
    ]
    assert "'retired'" in cancel_block
    assert "cancelled.status === 'retired'" in index
    assert "had already expired" in index
    assert 'concierge-completions.js?v=195' in index
