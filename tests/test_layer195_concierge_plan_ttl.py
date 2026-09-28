import json

from services.foundation_companion_service import (
    _safe_foundation_retirement,
    _supersede_previous_concierge_jobs,
    cancel_foundation_concierge_request_as_user,
    invoke_foundation_orchestration,
    set_pending_concierge_job_status,
)
from services import concierge_execution_service as execution_service


USER = "11111111-1111-4111-8111-111111111111"
REQUEST = "22222222-2222-4222-8222-222222222222"
OLD = "33333333-3333-4333-8333-333333333333"
LINK = "44444444-4444-4444-8444-444444444444"
CONVERSATION = "55555555-5555-4555-8555-555555555555"


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
    def __init__(self, rows=None, local_intent=None):
        self.tables = {
            "companion_foundation_pending_jobs": list(rows or []),
        }
        self.calls = []
        self.local_intent = local_intent

    def table(self, name):
        return Query(self, name)

    def rpc(self, name, params=None):
        params = params or {}
        self.calls.append((name, params))
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
            request_id = params["p_request_id"]
            for row in self.tables["companion_foundation_pending_jobs"]:
                if row.get("job_id") == request_id:
                    row["status"] = "retired"
                    row["retirement_reason"] = params["p_reason_code"]
                    row["retired_at"] = params["p_retired_at"]
                    row["retirement_receipt_sha256"] = params["p_receipt_sha256"]
            return Rpc({"status": "retired", "requestId": request_id})
        if name == "companion_begin_local_concierge_cancel_v1":
            if self.local_intent is not None:
                return Rpc(self.local_intent)
            raise AssertionError(name)
        raise AssertionError(name)


class Response:
    def __init__(self, code, payload):
        self.status_code = code
        self.payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {"content-length": str(len(self.content))}

    def json(self):
        return self.payload


def retirement(request_id=REQUEST):
    return {
        "status": "retired",
        "reasonCode": "unused-plan-expired",
        "requestId": request_id,
        "retiredAt": "2026-09-28T06:00:00Z",
        "receiptSha256": "a" * 64,
        "receipt": {
            "retirementReceipt": "shine-foundation/concierge-retirement-receipt-v1",
            "schemaVersion": "1.0.0",
            "requestId": request_id,
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
        "capability": "foundation_orchestration",
        "status": "ready",
        "handled": False,
        "reply": "",
        "foundation_orchestration": {
            "status": "ready",
            "selected_capabilities": ["travel.plan_trip"],
            "steps": [{
                "capability_id": "travel.plan_trip",
                "app_name": "Shine Travel",
                "display_name": "Plan a trip",
                "status": "ready",
                "reason_code": "specialist-ready",
                "runtime_available": True,
                "executable": True,
                "input_contract": {
                    "status": "ready",
                    "input_data": {"destination": "Vanuatu"},
                },
            }],
        },
    }


def test_foundation_blocked_expiry_projects_as_retired_with_no_execution():
    db = FakeDb()

    def post(url, *, json, **kwargs):
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

    result = invoke_foundation_orchestration(
        db,
        USER,
        request_id=REQUEST,
        orchestration_plan=route()["foundation_orchestration"],
        source_conversation_id=CONVERSATION,
        source_message_id=REQUEST,
        request_text="Plan Vanuatu",
        post_impl=post,
    )

    assert result["status"] == "retired"
    assert result["reason_code"] == "concierge-plan-expired"
    assert result["foundation_status"] == "blocked"
    assert result["execution_performed"] is False
    assert result["executed_capabilities"] == []
    assert result["retirement"]["reason_code"] == "unused-plan-expired"
    assert result["retirement"]["receipt_sha256"] == "a" * 64


def test_execute_route_marks_local_snapshot_retired_immediately(monkeypatch):
    db = FakeDb([{
        "job_id": REQUEST,
        "user_id": USER,
        "status": "ready",
    }])
    projected = {
        "status": "retired",
        "reason_code": "concierge-plan-expired",
        "foundation_status": "blocked",
        "request_id": REQUEST,
        "selected_capabilities": ["travel.plan_trip"],
        "executed_capabilities": [],
        "completed_capabilities": [],
        "unavailable_capabilities": ["travel.plan_trip"],
        "skipped_capabilities": [],
        "results": [],
        "execution_performed": False,
        "retirement": _safe_foundation_retirement(retirement(), REQUEST),
        "synthesis_ready": False,
        "synthesis_must_disclose_partial": False,
    }
    monkeypatch.setattr(
        execution_service,
        "invoke_foundation_orchestration",
        lambda *args, **kwargs: projected,
    )

    result = execution_service.execute_concierge_route(
        db,
        USER,
        request_id=REQUEST,
        route=route(),
    )

    assert result["status"] == "retired"
    assert result["local_retry_state"] == "retired"
    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "retired"
    mark = next(call for call in db.calls if call[0] == "companion_mark_local_concierge_retired_v1")
    assert mark[1]["p_reason_code"] == "unused-plan-expired"


def test_explicit_cancel_short_circuits_when_local_job_already_retired():
    db = FakeDb(local_intent={
        "status": "retired",
        "requestId": REQUEST,
        "reasonCode": "unused-plan-expired",
        "retiredAt": "2026-09-28T06:00:00Z",
        "receiptSha256": "a" * 64,
    })

    def forbidden(*args, **kwargs):
        raise AssertionError("retired local job must not call Foundation cancel")

    result = cancel_foundation_concierge_request_as_user(
        db,
        USER,
        request_id=REQUEST,
        authorization="Bearer " + "u" * 64,
        post_impl=forbidden,
    )

    assert result["status"] == "retired"
    assert result["reason_code"] == "unused-plan-expired"
    assert result["receipt_sha256"] == "a" * 64


def test_supersession_skips_already_retired_local_duplicate_without_network():
    old_inputs = {"travel.plan_trip": {"destination": "Vanuatu"}}
    from services.foundation_companion_service import _concierge_work_fingerprint

    db = FakeDb(
        rows=[{
            "job_id": OLD,
            "user_id": USER,
            "status": "ready",
            "source_conversation_id": CONVERSATION,
            "work_fingerprint": _concierge_work_fingerprint(
                CONVERSATION,
                ["travel.plan_trip"],
                old_inputs,
            ),
        }],
        local_intent={
            "status": "retired",
            "requestId": OLD,
            "reasonCode": "unused-plan-expired",
            "retiredAt": "2026-09-28T06:00:00Z",
            "receiptSha256": "a" * 64,
        },
    )

    result = _supersede_previous_concierge_jobs(
        db,
        user_id=USER,
        new_request_id=REQUEST,
        source_conversation_id=CONVERSATION,
        capability_ids=["travel.plan_trip"],
        inputs=old_inputs,
        client_token="c" * 128,
        delegation_token="d" * 128,
        foundation_url=None,
        timeout_seconds=12.0,
        post_impl=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("retired duplicate must not call Foundation supersede")
        ),
    )

    assert result == []


def test_invalid_retirement_receipt_fails_closed():
    bad = retirement()
    bad["receipt"]["executionStarted"] = True
    assert _safe_foundation_retirement(bad, REQUEST) is None



def test_late_local_state_write_cannot_overwrite_retired():
    db = FakeDb([{
        "job_id": REQUEST,
        "user_id": USER,
        "status": "retired",
    }])

    changed = set_pending_concierge_job_status(
        db,
        user_id=USER,
        job_id=REQUEST,
        status="failed",
    )

    assert changed is False
    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "retired"
