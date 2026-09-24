"""Exercise moving ledger pages through the pinned Supabase HTTP client."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import re
from uuid import UUID

import httpx
import pytest
from supabase import create_client
from supabase.lib.client_options import SyncClientOptions

from core.cognition import durable_task_ledger_audit as ledger
from core.cognition.durable_tasks import owner_identity, request_hash


TOKEN = "layer113-test-owner-no-production-access" * 2
NOW = datetime(2026, 9, 24, 3, tzinfo=timezone.utc)


def row(n, created_at="2026-09-24T01:00:00Z"):
    request_id = str(UUID(int=n))
    request = {"request_id": request_id, "message": "private fixture request"}
    return {
        "request_id": request_id, "request": request,
        "owner_hash": owner_identity(TOKEN)[1], "input_hash": request_hash(request),
        "status": "queued", "checkpoint": "queued", "worker_id": None,
        "lease_until": None, "result": None,
        "created_at": created_at, "updated_at": created_at,
    }


def moment(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW
    monkeypatch.setattr(ledger, "datetime", Clock)


@pytest.fixture
def run_scan():
    def run(responder, **kwargs):
        with httpx.Client(transport=httpx.MockTransport(responder)) as transport:
            client = create_client(
                "https://example.supabase.co", "fixture-key",
                options=SyncClientOptions(httpx_client=transport,
                                          auto_refresh_token=False, persist_session=False),
            )
            return ledger.load_task_ledger_audit(client, TOKEN, **kwargs)
    return run


class MovingLedger:
    """In-memory service interprets the real client's query, including filters."""

    def __init__(self, rows, on_page=None):
        self.rows = deepcopy(rows)
        self.requests = []
        self.on_page = on_page
        self.returned_ids = []

    def __call__(self, request):
        self.requests.append(request)
        if self.on_page:
            self.on_page(self, len(self.requests))
        params = request.url.params
        assert request.method == "GET"
        assert request.url.path == "/rest/v1/l_chat_tasks"
        assert "offset" not in params and "range" not in request.headers
        user_id, owner_hash = owner_identity(TOKEN)
        assert params["user_id"] == "eq." + user_id
        assert params["owner_hash"] == "eq." + owner_hash
        assert params["order"] == "created_at.asc,request_id.asc"
        assert params["created_at"] == "lte." + NOW.isoformat()
        assert TOKEN not in str(request.url)
        rows = [r for r in self.rows if moment(r["created_at"]) <= NOW]
        rows.sort(key=lambda r: (moment(r["created_at"]), UUID(r["request_id"])))
        if "or" in params:
            match = re.fullmatch(
                r"\(created_at.gt.([^,]+),and\(created_at.eq.([^,]+),request_id.gt.([^)]+)\)\)",
                params["or"],
            )
            assert match, params["or"]
            after, equal, last_id = match.groups()
            assert after == equal
            assert after == moment(after).astimezone(timezone.utc).isoformat()
            cursor = moment(after), UUID(last_id)
            rows = [r for r in rows if (moment(r["created_at"]), UUID(r["request_id"])) > cursor]
        page = rows[:int(params["limit"])]
        self.returned_ids.extend(r["request_id"] for r in page)
        return httpx.Response(200, json=page, request=request)


def test_deletion_before_cursor_does_not_skip_the_next_task(run_scan):
    def delete_seen(db, page):
        if page == 2:
            db.rows = [r for r in db.rows if r["request_id"] != row(1)["request_id"]]
    database = MovingLedger([row(i) for i in range(1, 6)], delete_seen)
    report = run_scan(database, page_size=2)
    assert database.returned_ids == [row(i)["request_id"] for i in range(1, 6)]
    assert report["tasks_observed"] == 5
    assert report["status"] == "complete_healthy"
    assert report["scan"]["pages_read"] == 3
    assert not any(report["actions"].values())


def test_insert_before_cursor_does_not_repeat_a_task_or_claim_a_snapshot(run_scan):
    def insert_earlier(db, page):
        if page == 2:
            db.rows.append(row(1))
    database = MovingLedger([row(i) for i in range(2, 7)], insert_earlier)
    report = run_scan(database, page_size=2)
    assert database.returned_ids == [row(i)["request_id"] for i in range(2, 7)]
    assert report["tasks_observed"] == 5
    assert report["scan"]["transactional_snapshot"] is False
    assert "backdated inserts" in " ".join(report["limitations"])


def test_new_tasks_after_start_are_excluded_and_boundary_is_reported(run_scan):
    def insert_later(db, page):
        if page == 2:
            db.rows.append(row(99, (NOW + timedelta(seconds=1)).isoformat()))
    database = MovingLedger([row(1), row(2), row(3, NOW.isoformat())], insert_later)
    report = run_scan(database, page_size=2)
    assert report["tasks_observed"] == 3
    assert row(99)["request_id"] not in database.returned_ids
    assert report["scan"]["created_at_upper_bound"] == NOW.isoformat()
    assert report["claims"]["ledger_coverage_scope"] == "recovery_token_owner_tasks_created_by_scan_start"


def test_equal_timestamps_and_timezone_offsets_visit_each_row_once(run_scan):
    rows = [row(30, "2026-09-24T10:59:59+10:00"), row(4),
            row(2, "2026-09-24T11:00:00+10:00"), row(1, "2026-09-24T01:00:01Z")]
    database = MovingLedger(rows)
    report = run_scan(database, page_size=1)
    assert database.returned_ids == [row(i)["request_id"] for i in (30, 2, 4, 1)]
    assert report["status"] == "complete_healthy"
    assert report["scan"]["pages_read"] == 5  # Includes the empty end probe.


@pytest.mark.parametrize("count,max_rows,capped", [(0, 10, False), (3, 10, False),
                                                   (4, 4, True), (5, 4, True), (4, 3, True)])
def test_empty_short_and_capped_scans_have_honest_coverage(run_scan, count, max_rows, capped):
    database = MovingLedger([row(i) for i in range(1, count + 1)])
    report = run_scan(database, page_size=2, max_rows=max_rows)
    assert report["tasks_observed"] == min(count, max_rows)
    assert report["capped"] is capped
    assert report["scan_complete"] is not capped
    assert report["claims"]["ledger_consistency"] == ("not_verified" if capped else "verified")
    assert report["scan"]["rows_read"] <= max_rows


@pytest.mark.parametrize("field,value", [
    ("request_id", "private),owner_hash.neq.secret"),
    ("created_at", "private),owner_hash.neq.secret"),
    ("created_at", "2026-09-24T01:00:00"),
])
def test_invalid_cursor_stops_without_interpolating_stored_content(run_scan, field, value):
    requests = []
    item = row(1)
    item[field] = value
    def responder(request):
        requests.append(request)
        return httpx.Response(200, json=[item], request=request)
    report = run_scan(responder, page_size=1)
    assert len(requests) == 1
    assert report["scan"]["error"] == "invalid_scan_key"
    assert report["status"] == "incomplete_scan"
    assert report["invalid_task_rows"] == 1
    assert report["claims"]["ledger_consistency"] == "not_verified"
    assert "private" not in json.dumps(report)
    assert "private" not in str(requests[0].url)


@pytest.mark.parametrize("bad_page,error,observed", [
    ([row(2), row(3)], "non_advancing_scan_key", 2),
    ([row(4), row(3)], "non_advancing_scan_key", 3),
    ([row(3, "2026-09-24T04:00:00Z")], "scan_boundary_exceeded", 2),
    ([row(3), row(4), row(5)], "page_size_exceeded", 2),
    (["private malformed row"], "invalid_scan_key", 2),
])
def test_broken_page_contract_cannot_certify_or_loop(run_scan, bad_page, error, observed):
    requests = []
    def responder(request):
        requests.append(request)
        page = [row(1), row(2)] if len(requests) == 1 else bad_page
        return httpx.Response(200, json=page, request=request)
    report = run_scan(responder, page_size=2)
    assert len(requests) == 2
    assert report["scan"]["error"] == error
    assert report["tasks_observed"] == observed
    assert report["scan_complete"] is False
    assert report["claims"]["ledger_consistency"] == "not_verified"
    assert "private" not in json.dumps(report)


def test_report_does_not_disclose_cursor_payload_or_token(run_scan):
    item = row(11223344)
    item["status"] = "private invalid status"
    database = MovingLedger([item])
    report = run_scan(database, page_size=1)
    encoded = json.dumps(report)
    for secret in (TOKEN, item["request_id"], item["owner_hash"], item["input_hash"], "private"):
        assert secret not in encoded
    assert report["status"] == "complete_with_ledger_issues"
    assert report["task_statuses"] == {"invalid": 1}


def test_http_route_reports_new_scan_metadata_and_rejects_invalid_owner(monkeypatch):
    from fastapi.testclient import TestClient
    from api import server

    database = MovingLedger([row(1)])
    with httpx.Client(transport=httpx.MockTransport(database)) as transport:
        client = create_client("https://example.supabase.co", "fixture-key", options=SyncClientOptions(
            httpx_client=transport, auto_refresh_token=False, persist_session=False,
        ))
        monkeypatch.setattr(server.task_store, "client", client)
        # No application lifespan: starting workers is outside this read-only test.
        api = TestClient(server.app)
        assert api.get("/cognition/durable-task-ledger-audit").status_code == 401
        assert not database.requests
        # Supply a verified-account fixture; owner-token validation stays real.
        monkeypatch.setattr(server, "require_account", lambda *_: {"id": "fixture-account"})
        response = api.get("/cognition/durable-task-ledger-audit?page_size=1",
                           headers={"x-l-recovery-token": TOKEN})
        assert response.status_code == 200
        assert response.json()["scan"]["pagination"] == "created_at_request_id_keyset"
        assert response.json()["version"] == ledger.VERSION
        count = len(database.requests)
        assert api.get("/cognition/durable-task-ledger-audit").status_code == 400
        assert len(database.requests) == count


def test_database_failure_does_not_return_a_partial_healthy_audit(monkeypatch):
    from api import server
    from fastapi import HTTPException

    def responder(request):
        return httpx.Response(503, json={"message": "private backend failure"}, request=request)
    with httpx.Client(transport=httpx.MockTransport(responder)) as transport:
        client = create_client("https://example.supabase.co", "fixture-key", options=SyncClientOptions(
            httpx_client=transport, auto_refresh_token=False, persist_session=False,
        ))
        monkeypatch.setattr(server.task_store, "client", client)
        with pytest.raises(HTTPException) as exc:
            server.cognition_durable_task_ledger_audit(page_size=2, max_rows=10, x_l_recovery_token=TOKEN)
    assert exc.value.status_code == 503
    assert "private" not in exc.value.detail
