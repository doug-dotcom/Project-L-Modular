import json

from services.foundation_companion_service import (
    _concierge_work_fingerprint,
    _supersede_previous_concierge_jobs,
    cancel_foundation_concierge_request_as_user,
)


USER = "11111111-1111-4111-8111-111111111111"
OLD = "22222222-2222-4222-8222-222222222222"
NEW = "33333333-3333-4333-8333-333333333333"
CONVERSATION = "44444444-4444-4444-8444-444444444444"


class Result:
    def __init__(self, data):
        self.data = data


class Rpc:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return Result(self.data)


class Query:
    def __init__(self, db, table):
        self.db = db
        self.table_name = table
        self.filters = {}
        self.not_filters = {}
        self.limit_value = None

    def select(self, *args):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def neq(self, key, value):
        self.not_filters[key] = value
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        rows = [
            dict(row)
            for row in self.db.tables.get(self.table_name, [])
            if all(str(row.get(k)) == str(v) for k, v in self.filters.items())
            and all(str(row.get(k)) != str(v) for k, v in self.not_filters.items())
        ]
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        return Result(rows)


class FakeDb:
    def __init__(self, rows):
        self.tables = {
            "companion_foundation_pending_jobs": [dict(row) for row in rows],
            "companion_concierge_completion_outbox": [],
        }

    def table(self, name):
        return Query(self, name)

    def rpc(self, name, params=None):
        params = params or {}
        if name in {
            "companion_begin_local_concierge_cancel_v1",
            "companion_finish_local_concierge_cancel_v1",
        }:
            for row in self.tables["companion_foundation_pending_jobs"]:
                if (
                    row["job_id"] == params["p_request_id"]
                    and row["user_id"] == params["p_user_id"]
                ):
                    if row["status"] in {"completed", "failed"}:
                        return Rpc({"status": row["status"], "requestId": row["job_id"]})

                    if name == "companion_begin_local_concierge_cancel_v1":
                        if row["status"] == "cancelled":
                            return Rpc({
                                "status": "already-cancelled",
                                "requestId": row["job_id"],
                            })
                        row["status"] = "cancelling"
                        row["cancellation_reason"] = params["p_reason_code"]
                        row["superseded_by_request_id"] = params["p_superseded_by_request_id"]
                        return Rpc({
                            "status": "cancelling",
                            "requestId": row["job_id"],
                            "reasonCode": params["p_reason_code"],
                            "supersededByRequestId": params["p_superseded_by_request_id"],
                        })

                    assert row["status"] == "cancelling"
                    assert row["cancellation_reason"] == params["p_reason_code"]
                    assert row.get("superseded_by_request_id") == params["p_superseded_by_request_id"]
                    row["status"] = "cancelled"
                    return Rpc({
                        "status": "cancelled",
                        "requestId": row["job_id"],
                        "reasonCode": params["p_reason_code"],
                        "supersededByRequestId": params["p_superseded_by_request_id"],
                    })
            return Rpc({"status": "not-found"})
        raise AssertionError(name)


class Response:
    def __init__(self, status, payload):
        self.status_code = status
        self.payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {"content-length": str(len(self.content))}

    def json(self):
        return self.payload


def pending_row(*, status="ready", conversation=CONVERSATION):
    capabilities = ["travel.plan_trip"]
    inputs = {"travel.plan_trip": {"destination": "Vanuatu"}}
    return {
        "job_id": OLD,
        "user_id": USER,
        "source_conversation_id": conversation,
        "status": status,
        "capability_ids": capabilities,
        "inputs": inputs,
        "work_fingerprint": _concierge_work_fingerprint(
            conversation,
            capabilities,
            inputs,
        ),
    }


def test_work_fingerprint_is_exact_and_conversation_bound():
    capabilities = ["travel.plan_trip", "dive.destination_brief"]
    inputs = {
        "travel.plan_trip": {"destination": "Vanuatu"},
        "dive.destination_brief": {"destination": "Vanuatu"},
    }
    same = _concierge_work_fingerprint(CONVERSATION, capabilities, inputs)
    assert same == _concierge_work_fingerprint(CONVERSATION, capabilities, inputs)
    assert same == _concierge_work_fingerprint(
        CONVERSATION,
        list(reversed(capabilities)),
        inputs,
    )
    assert same != _concierge_work_fingerprint(NEW, capabilities, inputs)
    assert same != _concierge_work_fingerprint(
        CONVERSATION,
        capabilities,
        {**inputs, "travel.plan_trip": {"destination": "Fiji"}},
    )


def test_exact_pending_work_is_superseded_in_foundation_then_locally():
    row = pending_row()
    db = FakeDb([row])
    calls = []

    def post(url, *, json, **kwargs):
        calls.append((url, json))
        assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "cancelling"
        assert url.endswith("/v1/concierge/supersede")
        assert json["requestId"] == OLD
        assert json["supersededByRequestId"] == NEW
        return Response(200, {
            "status": "superseded",
            "reasonCode": "superseded-by-newer-request",
        })

    superseded = _supersede_previous_concierge_jobs(
        db,
        user_id=USER,
        new_request_id=NEW,
        source_conversation_id=CONVERSATION,
        capability_ids=row["capability_ids"],
        inputs=row["inputs"],
        client_token="c" * 128,
        delegation_token="d" * 128,
        foundation_url="https://foundation.example",
        timeout_seconds=12,
        post_impl=post,
    )

    assert superseded == [OLD]
    assert len(calls) == 1
    saved = db.tables["companion_foundation_pending_jobs"][0]
    assert saved["status"] == "cancelled"
    assert saved["cancellation_reason"] == "superseded-by-newer-request"
    assert saved["superseded_by_request_id"] == NEW


def test_legacy_conversation_label_never_auto_supersedes():
    row = pending_row(conversation="doug_primary")
    db = FakeDb([row])

    def forbidden(*args, **kwargs):
        raise AssertionError("legacy conversation must not auto-cancel")

    superseded = _supersede_previous_concierge_jobs(
        db,
        user_id=USER,
        new_request_id=NEW,
        source_conversation_id="doug_primary",
        capability_ids=row["capability_ids"],
        inputs=row["inputs"],
        client_token="c" * 128,
        delegation_token="d" * 128,
        foundation_url="https://foundation.example",
        timeout_seconds=12,
        post_impl=forbidden,
    )
    assert superseded == []
    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "cancelling"


def test_user_cancel_requires_remote_confirmation_before_local_cancel():
    db = FakeDb([pending_row()])
    calls = []

    def post(url, *, headers, json, **kwargs):
        calls.append((url, headers, json))
        assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "cancelling"
        assert url.endswith("/v1/concierge/cancel")
        assert headers["Authorization"].startswith("Bearer ")
        assert json["requestId"] == OLD
        return Response(200, {
            "status": "cancelled",
            "reasonCode": "user-cancelled",
        })

    result = cancel_foundation_concierge_request_as_user(
        db,
        USER,
        request_id=OLD,
        authorization="Bearer " + "x" * 100,
        foundation_url="https://foundation.example",
        post_impl=post,
    )
    assert result["status"] == "cancelled"
    assert len(calls) == 1
    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "cancelled"


def test_terminal_job_is_never_sent_to_remote_cancel():
    for terminal in ("completed", "failed"):
        db = FakeDb([pending_row(status=terminal)])

        def forbidden(*args, **kwargs):
            raise AssertionError("terminal job must not be remotely cancelled")

        result = cancel_foundation_concierge_request_as_user(
            db,
            USER,
            request_id=OLD,
            authorization="Bearer " + "x" * 100,
            foundation_url="https://foundation.example",
            post_impl=forbidden,
        )
        assert result["status"] == terminal


def test_ui_exposes_pending_jobs_and_cancel_only_for_delayed_work():
    from pathlib import Path

    bridge = Path("ui/concierge-completions.js").read_text(encoding="utf-8")
    index = Path("ui/index.html").read_text(encoding="utf-8")
    api = Path("api/foundation_companion.py").read_text(encoding="utf-8")

    assert "async function pendingJobs" in bridge
    assert "async function cancelPending" in bridge
    assert "pending: (limit = 100) => pendingJobs(limit)" in bridge
    assert "cancel: requestId => cancelPending(requestId)" in bridge

    assert "pendingConcierge: new Map()" in index
    assert "Cancel delayed work" in index
    assert "window.lConciergeCompletions?.cancel?.(task.requestId)" in index
    assert "The saved answer above has not been rewritten." in index
    assert "Retry cancellation" in index
    assert "Cancellation is pending confirmation" in index
    assert 'concierge-completions.js?v=193' in index

    assert '@router.get("/completions/pending")' in api
    assert '@router.post("/completions/{request_id}/cancel")' in api



def test_remote_already_cancelled_for_other_reason_is_not_relabelled_as_superseded():
    row = pending_row()
    db = FakeDb([row])

    def post(url, **kwargs):
        return Response(200, {
            "status": "already-superseded",
            "reasonCode": "user-cancelled",
        })

    try:
        _supersede_previous_concierge_jobs(
            db,
            user_id=USER,
            new_request_id=NEW,
            source_conversation_id=CONVERSATION,
            capability_ids=row["capability_ids"],
            inputs=row["inputs"],
            client_token="c" * 128,
            delegation_token="d" * 128,
            foundation_url="https://foundation.example",
            timeout_seconds=12,
            post_impl=post,
        )
    except RuntimeError as exc:
        assert "user-cancelled" in str(exc)
    else:
        raise AssertionError("non-supersession cancellation reason must fail closed")

    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "ready"



def test_user_cancel_network_uncertainty_leaves_safe_cancelling_hold():
    db = FakeDb([pending_row()])

    def post(*args, **kwargs):
        assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "cancelling"
        raise RuntimeError("ack lost")

    result = cancel_foundation_concierge_request_as_user(
        db,
        USER,
        request_id=OLD,
        authorization="Bearer " + "x" * 100,
        foundation_url="https://foundation.example",
        post_impl=post,
    )

    assert result["status"] == "cancelling"
    assert result["reason_code"] == "cancellation-acknowledgement-unavailable"
    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "cancelling"


def test_begin_cancel_is_idempotent_before_remote_reconciliation():
    db = FakeDb([pending_row()])

    first = db.rpc("companion_begin_local_concierge_cancel_v1", {
        "p_user_id": USER,
        "p_request_id": OLD,
        "p_reason_code": "user-cancelled",
        "p_superseded_by_request_id": None,
    }).execute().data
    second = db.rpc("companion_begin_local_concierge_cancel_v1", {
        "p_user_id": USER,
        "p_request_id": OLD,
        "p_reason_code": "user-cancelled",
        "p_superseded_by_request_id": None,
    }).execute().data

    assert first["status"] == "cancelling"
    assert second["status"] == "cancelling"
    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "cancelling"
