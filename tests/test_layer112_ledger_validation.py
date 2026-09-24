"""Malformed ledger records must be diagnosable without crashes or content leaks."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from core.cognition.durable_task_ledger_audit import (
    audit_task_row, load_task_ledger_audit, summarise_task_ledger,
)
from core.cognition.durable_tasks import owner_identity, request_hash


TOKEN = "layer112-fixture-token-not-a-real-owner" * 2
NOW = datetime(2026, 9, 24, 2, tzinfo=timezone.utc)
REQUEST_ID = "abcdefab-1234-4234-8234-123456789abc"


def row():
    request = {"request_id": REQUEST_ID, "message": "private fixture text"}
    return {
        "request_id": REQUEST_ID, "request": request,
        "owner_hash": owner_identity(TOKEN)[1], "input_hash": request_hash(request),
        "status": "queued", "checkpoint": "queued", "worker_id": None,
        "lease_until": None, "result": None,
        "created_at": "2026-09-24T01:00:00Z",
        "updated_at": "2026-09-24T01:00:01+00:00",
    }


@pytest.mark.parametrize("field", ["created_at", "updated_at", "lease_until"])
@pytest.mark.parametrize("value", ["2026-09-24T01:00:00", "2026-09-24", "invalid", 42])
def test_invalid_or_naive_dates_report_issues_without_aborting(field, value):
    item = row()
    item.update(status="running", checkpoint="generating", worker_id=REQUEST_ID,
                lease_until="2026-09-24T02:01:00Z")
    item[field] = value
    report = summarise_task_ledger([item, row()], scan_complete=True, capped=False, now=NOW)
    assert report["status"] == "complete_with_ledger_issues"
    assert report["valid_task_rows"] == 1
    assert report["invalid_task_rows"] == 1
    assert report["claims"]["ledger_consistency"] == "not_verified"


def test_timezone_offsets_and_exact_lease_boundary_match_queue_contract():
    item = row()
    item.update(status="running", checkpoint="generating", worker_id=REQUEST_ID,
                created_at="2026-09-24T11:00:00+10:00",
                updated_at="2026-09-24T01:00:01Z", lease_until=NOW.isoformat())
    assert audit_task_row(item, now=NOW)["valid"]
    item["lease_until"] = "2026-09-24T01:59:59Z"
    assert "running_task_lease_expired" in audit_task_row(item, now=NOW)["issues"]


@pytest.mark.parametrize("field,value,issue", [
    ("request_id", None, "request_id_invalid"),
    ("request_id", "not-a-uuid", "request_id_invalid"),
    ("owner_hash", "o" * 64, "owner_hash_shape_invalid"),
    ("owner_hash", 1, "owner_hash_shape_invalid"),
    ("input_hash", "g" * 64, "input_hash_shape_invalid"),
    ("worker_id", "not-a-uuid", "worker_id_invalid"),
    ("checkpoint", "   ", "checkpoint_missing"),
    ("checkpoint", "generating", "queued_checkpoint_mismatch"),
])
def test_identifiers_hashes_and_checkpoints_are_validated(field, value, issue):
    item = row()
    item[field] = value
    assert issue in audit_task_row(item, now=NOW)["issues"]


@pytest.mark.parametrize("value", [None, "", {}, "not-a-uuid"])
def test_missing_or_invalid_embedded_id_cannot_pass_with_matching_hash(value):
    item = row()
    item["request"]["request_id"] = value
    item["input_hash"] = request_hash(item["request"])
    audit = audit_task_row(item, now=NOW)
    assert not audit["valid"]
    assert "request_payload_id_invalid" in audit["issues"]


def test_absent_embedded_id_is_invalid_but_equivalent_uuid_spelling_is_valid():
    item = row()
    del item["request"]["request_id"]
    item["input_hash"] = request_hash(item["request"])
    assert "request_payload_id_invalid" in audit_task_row(item, now=NOW)["issues"]
    item["request"]["request_id"] = REQUEST_ID.upper()
    item["input_hash"] = request_hash(item["request"])
    assert audit_task_row(item, now=NOW)["valid"]


@pytest.mark.parametrize("status", ["queued", "interrupted", "ready"])
def test_malformed_present_lease_cannot_masquerade_as_absent(status):
    item = row()
    item.update(status=status, checkpoint=status, lease_until="private invalid lease")
    if status == "ready":
        item["result"] = {"sealed": "fixture"}
    audit = audit_task_row(item, now=NOW)
    assert "lease_until_invalid" in audit["issues"]
    assert "private invalid lease" not in json.dumps(audit)
    if status == "queued":
        assert "queued_task_has_lease" in audit["issues"]


@pytest.mark.parametrize("status", ["private injected status", {"secret": "private injected status"}, []])
def test_arbitrary_status_content_is_never_echoed(status):
    item = row()
    item["status"] = status
    report = summarise_task_ledger([item], scan_complete=True, capped=False, now=NOW)
    assert report["task_statuses"] == {"invalid": 1}
    assert report["findings"][0]["status"] == "invalid"
    assert "private" not in json.dumps(report)
    assert REQUEST_ID not in json.dumps(report)
    assert report["claims"]["ledger_consistency"] == "not_verified"


def test_large_failure_set_keeps_counts_and_reports_omitted_findings():
    items = []
    for _ in range(75):
        item = row()
        item["created_at"] = "invalid"
        items.append(item)
    report = summarise_task_ledger(items + [None, "private malformed row"],
                                 scan_complete=True, capped=False, now=NOW)
    assert report["invalid_task_rows"] == 75
    assert report["malformed_rows"] == 2
    assert len(report["findings"]) == 50
    assert report["findings_omitted"] == 25
    assert report["issue_codes"]["created_at_invalid"] == 75
    assert "private" not in json.dumps(report)


def test_real_postgrest_query_is_owner_scoped_and_breaks_timestamp_ties():
    import httpx
    from supabase import create_client
    from supabase.lib.client_options import SyncClientOptions

    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=[row()], request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        client = create_client("https://example.supabase.co", "fixture-key", options=SyncClientOptions(
            httpx_client=transport, auto_refresh_token=False, persist_session=False,
        ))
        report = load_task_ledger_audit(client, TOKEN)
    assert report["status"] == "complete_healthy"
    assert len(requests) == 1
    request = requests[0]
    assert request.method == "GET"
    assert request.url.params["order"] == "created_at.asc,request_id.asc"
    user_id, owner_hash = owner_identity(TOKEN)
    assert request.url.params["user_id"] == "eq." + user_id
    assert request.url.params["owner_hash"] == "eq." + owner_hash
    assert TOKEN not in str(request.url)


def test_endpoint_returns_diagnostics_for_malformed_record(monkeypatch):
    from api import server

    item = row()
    item["updated_at"] = "2026-09-24T01:00:01"
    class Query:
        def select(self, *_): return self
        def eq(self, *_): return self
        def order(self, *_, **__): return self
        def range(self, *_): return self
        def execute(self): return SimpleNamespace(data=[item])
    monkeypatch.setattr(server.task_store, "client", SimpleNamespace(table=lambda _: Query()))
    report = server.cognition_durable_task_ledger_audit(
        page_size=100, max_rows=10000, x_l_recovery_token=TOKEN,
    )
    assert report["status"] == "complete_with_ledger_issues"
    assert report["issue_codes"]["updated_at_invalid"] == 1
    assert not any(report["actions"].values())
