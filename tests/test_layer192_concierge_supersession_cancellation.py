import json

from services.foundation_companion_service import (
    _concierge_work_fingerprint,
    cancel_foundation_concierge_request_as_user,
    invoke_foundation_orchestration,
)
from services.concierge_retry_service import run_concierge_retry_once


USER = "11111111-1111-4111-8111-111111111111"
LINK = "22222222-2222-4222-8222-222222222222"
OLD = "33333333-3333-4333-8333-333333333333"
NEW = "44444444-4444-4444-8444-444444444444"
CONVERSATION = "55555555-5555-4555-8555-555555555555"
RETRY = "66666666-6666-4666-8666-666666666666"
CLAIM = "77777777-7777-4777-8777-777777777777"


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
        q = Query(self.db, self.table_name, "update", payload)
        return q

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
    def __init__(self, rows=None):
        self.tables = {
            "companion_foundation_pending_jobs": list(rows or []),
            "companion_concierge_completion_outbox": [],
        }

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
        if name == "companion_cancel_local_concierge_job_v2":
            request_id = params["p_request_id"]
            for row in self.tables["companion_foundation_pending_jobs"]:
                if row["job_id"] == request_id and row["user_id"] == params["p_user_id"]:
                    if row["status"] in {"completed", "failed"}:
                        return Rpc({"status": row["status"], "requestId": request_id})
                    if row["status"] == "cancelled":
                        return Rpc({
                            "status": "already-cancelled",
                            "requestId": request_id,
                            "reasonCode": row.get("cancellation_reason"),
                            "supersededByRequestId": row.get("superseded_by_request_id"),
                        })
                    row["status"] = "cancelled"
                    row["cancellation_reason"] = params["p_reason_code"]
                    row["superseded_by_request_id"] = params.get("p_superseded_by_request_id")
                    return Rpc({
                        "status": "cancelled",
                        "requestId": request_id,
                        "reasonCode": params["p_reason_code"],
                        "supersededByRequestId": params.get("p_superseded_by_request_id"),
                    })
            return Rpc({"status": "not-found", "requestId": request_id})
        raise AssertionError(name)


class Response:
    def __init__(self, code, payload):
        self.status_code = code
        self.payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {"content-length": str(len(self.content))}

    def json(self):
        return self.payload


def plan(destination="Vanuatu"):
    return {
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
                "input_data": {"destination": destination},
            },
        }],
    }


def old_job(destination="Vanuatu", status="ready"):
    capability_ids = ["travel.plan_trip"]
    inputs = {"travel.plan_trip": {"destination": destination}}
    return {
        "job_id": OLD,
        "user_id": USER,
        "link_request_id": LINK,
        "purpose": "concierge.cross-project-read",
        "capability_ids": capability_ids,
        "inputs": inputs,
        "source_conversation_id": CONVERSATION,
        "source_message_id": OLD,
        "request_text": f"Plan {destination}",
        "status": status,
        "work_fingerprint": _concierge_work_fingerprint(
            CONVERSATION, capability_ids, inputs
        ),
    }


def test_work_fingerprint_is_exact_not_fuzzy():
    ids = ["travel.plan_trip"]
    vanuatu = {"travel.plan_trip": {"destination": "Vanuatu"}}
    same = {"travel.plan_trip": {"destination": "Vanuatu"}}
    fiji = {"travel.plan_trip": {"destination": "Fiji"}}
    assert _concierge_work_fingerprint(CONVERSATION, ids, vanuatu) == (
        _concierge_work_fingerprint(CONVERSATION, ids, same)
    )
    assert _concierge_work_fingerprint(CONVERSATION, ids, vanuatu) != (
        _concierge_work_fingerprint(CONVERSATION, ids, fiji)
    )

    multi_inputs = {
        "travel.plan_trip": {"destination": "Vanuatu"},
        "dive.destination_brief": {"destination": "Vanuatu"},
    }
    assert _concierge_work_fingerprint(
        CONVERSATION,
        ["travel.plan_trip", "dive.destination_brief"],
        multi_inputs,
    ) == _concierge_work_fingerprint(
        CONVERSATION,
        ["dive.destination_brief", "travel.plan_trip"],
        multi_inputs,
    )


def test_new_identical_request_supersedes_old_before_execution():
    db = FakeDb([old_job()])
    calls = []

    def post(url, *, json, **kwargs):
        calls.append((url, json))
        if url.endswith("/v1/concierge/plan"):
            return Response(200, {"status": "planned", "reasonCode": "concierge-plan-created"})
        if url.endswith("/v1/concierge/supersede"):
            assert json["requestId"] == OLD
            assert json["supersededByRequestId"] == NEW
            return Response(200, {
                "status": "superseded",
                "reasonCode": "superseded-by-newer-request",
            })
        if url.endswith("/v1/concierge/execute"):
            return Response(200, {
                "status": "completed",
                "reasonCode": "concierge-execution-completed",
                "results": [{
                    "capabilityId": "travel.plan_trip",
                    "appId": "shine.travel",
                    "status": "completed",
                    "reasonCode": "capability-completed",
                    "result": {"summary": "Trip"},
                }],
                "synthesisReady": True,
                "synthesisMustDisclosePartial": False,
            })
        raise AssertionError(url)

    result = invoke_foundation_orchestration(
        db,
        USER,
        request_id=NEW,
        orchestration_plan=plan(),
        source_conversation_id=CONVERSATION,
        source_message_id=NEW,
        request_text="Plan Vanuatu",
        post_impl=post,
    )

    assert result["status"] == "completed"
    assert result["superseded_request_ids"] == [OLD]
    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "cancelled"
    assert db.tables["companion_foundation_pending_jobs"][0]["superseded_by_request_id"] == NEW
    assert [url for url, _ in calls].index(
        next(url for url, _ in calls if url.endswith("/supersede"))
    ) < [url for url, _ in calls].index(
        next(url for url, _ in calls if url.endswith("/execute"))
    )


def test_different_compiled_inputs_do_not_supersede_old_work():
    db = FakeDb([old_job("Vanuatu")])
    paths = []

    def post(url, *, json, **kwargs):
        paths.append(url)
        if url.endswith("/v1/concierge/plan"):
            return Response(200, {"status": "planned", "reasonCode": "concierge-plan-created"})
        if url.endswith("/v1/concierge/execute"):
            return Response(200, {
                "status": "completed",
                "reasonCode": "concierge-execution-completed",
                "results": [{
                    "capabilityId": "travel.plan_trip",
                    "appId": "shine.travel",
                    "status": "completed",
                    "reasonCode": "capability-completed",
                    "result": {"summary": "Fiji"},
                }],
                "synthesisReady": True,
                "synthesisMustDisclosePartial": False,
            })
        raise AssertionError(url)

    result = invoke_foundation_orchestration(
        db,
        USER,
        request_id=NEW,
        orchestration_plan=plan("Fiji"),
        source_conversation_id=CONVERSATION,
        source_message_id=NEW,
        request_text="Plan Fiji",
        post_impl=post,
    )
    assert result["status"] == "completed"
    assert result["superseded_request_ids"] == []
    assert not any(path.endswith("/supersede") for path in paths)
    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "ready"


def test_explicit_user_cancel_uses_user_bearer_and_preserves_terminal_jobs():
    db = FakeDb([old_job()])
    calls = []

    def post(url, *, headers, json, **kwargs):
        calls.append((url, headers, json))
        assert url.endswith("/v1/concierge/cancel")
        assert headers["Authorization"] == "Bearer " + "u" * 64
        return Response(200, {
            "status": "cancelled",
            "reasonCode": "user-cancelled",
        })

    result = cancel_foundation_concierge_request_as_user(
        db,
        USER,
        request_id=OLD,
        authorization="Bearer " + "u" * 64,
        post_impl=post,
    )
    assert result["status"] == "cancelled"
    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "cancelled"
    assert len(calls) == 1

    completed = FakeDb([old_job(status="completed")])
    result = cancel_foundation_concierge_request_as_user(
        completed,
        USER,
        request_id=OLD,
        authorization="Bearer " + "u" * 64,
        post_impl=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("completed job must not call Foundation cancel")
        ),
    )
    assert result["status"] == "completed"


def test_already_leased_retry_abandons_without_resume_after_local_cancel():
    job = old_job(status="cancelled")
    job["cancellation_reason"] = "superseded-by-newer-request"
    job["superseded_by_request_id"] = NEW
    db = FakeDb([job])
    calls = []

    def post(url, *, json, **kwargs):
        calls.append((url, json))
        if url.endswith("/retry/claim"):
            return Response(200, {
                "status": "ok",
                "reasonCode": "retry-claimed",
                "retry": {
                    "claimed": True,
                    "retryJobId": RETRY,
                    "requestId": OLD,
                    "ownerShineId": USER,
                    "clientId": "shine.companion",
                    "capabilityIds": ["travel.plan_trip"],
                    "attempt": 1,
                    "maxAttempts": 3,
                    "claimToken": CLAIM,
                    "expiresAt": "2026-09-29T00:00:00Z",
                },
            })
        if url.endswith("/retry/finish"):
            assert json["outcome"] == "abandoned"
            assert json["reasonCode"] == "superseded-by-newer-request"
            return Response(200, {
                "status": "ok",
                "reasonCode": "retry-finished",
                "retry": {"status": "abandoned"},
            })
        if url.endswith("/concierge/resume"):
            raise AssertionError("cancelled retry must never resume")
        raise AssertionError(url)

    result = run_concierge_retry_once(db, post_impl=post)
    assert result["status"] == "cancelled"
    assert result["reason_code"] == "superseded-by-newer-request"
    assert result["superseded_by_request_id"] == NEW
    assert not any(url.endswith("/concierge/resume") for url, _ in calls)


def test_saved_answers_exposes_cancel_delayed_work_only_for_pending_overlay():
    from pathlib import Path

    index = Path("ui/index.html").read_text(encoding="utf-8")
    completions = Path("ui/concierge-completions.js").read_text(encoding="utf-8")
    api = Path("api/foundation_companion.py").read_text(encoding="utf-8")

    assert "Cancel delayed work" in index
    assert "run.pendingConcierge.get(task.requestId)" in index
    assert "window.lConciergeCompletions?.cancel?.(task.requestId)" in index
    assert "The saved answer above has not been rewritten." in index
    assert 'concierge-completions.js?v=193' in index

    assert "async function pendingJobs" in completions
    assert "async function cancelPending" in completions
    assert "pending: (limit = 100) => pendingJobs(limit)" in completions
    assert "cancel: requestId => cancelPending(requestId)" in completions

    assert '@router.get("/completions/pending")' in api
    assert '@router.post("/completions/{request_id}/cancel")' in api
