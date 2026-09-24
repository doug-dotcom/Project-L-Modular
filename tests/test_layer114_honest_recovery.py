"""Recovery claims must include damaged records and never certify missing answers."""

import json
from types import SimpleNamespace

import pytest

from core.cognition import recovery_coverage_certification as coverage
from core.cognition.cold_recovery_certification import certify_saved_answer_row
from core.cognition.delivery_integrity import seal_chat_delivery_payload
from core.cognition.durable_tasks import TaskStore, owner_identity
from core.cognition.recovery_provenance import PROTOCOL_KEY, verify_recovered_answer_payload


RID = "00000000-0000-4000-8000-000000000114"
TOKEN = "layer114-test-owner-token" * 3
PRIVATE = "PRIVATE fixture answer must not leak"


def payload(**extra):
    return seal_chat_delivery_payload({"reply": PRIVATE, **extra}, request_id=RID)


def row(result, status="ready"):
    return {"request_id": RID, "result": result, "status": status,
            "created_at": "2026-09-24T00:00:00Z", "updated_at": "2026-09-24T00:00:01Z"}


def summary(rows, **bounds):
    return coverage.summarise_recovery_coverage(
        rows, current_release={}, scan_complete=bounds.get("scan_complete", True),
        capped=bounds.get("capped", False),
    )


@pytest.mark.parametrize("status", ["ready", "failed"])
@pytest.mark.parametrize("result", [None, "broken", [], 42])
def test_terminal_missing_or_malformed_answer_is_a_recovery_failure(status, result):
    item = row(result, status)
    cert = certify_saved_answer_row(item, request_id=RID, current_release={})
    assert cert["status"] == "failed_integrity"
    assert cert["claims"]["recoverability"] == "failed"
    report = summary([item])
    assert report["status"] == "complete_with_recovery_failures"
    assert report["not_ready_answers"] == 0
    assert report["failed_recovery_records"] == 1
    assert report["failed_ready_answers"] == (1 if status == "ready" else 0)
    assert not report["coverage"]["all_ready_answers_recoverable"]


@pytest.mark.parametrize("status", ["queued", "running", "interrupted"])
def test_real_incomplete_tasks_remain_distinct_from_missing_terminal_answers(status):
    report = summary([row(None, status)])
    assert report["status"] == "complete_with_incomplete_tasks"
    assert report["not_ready_answers"] == 1
    assert report["failed_recovery_records"] == 0
    assert report["coverage"]["all_ready_answers_recoverable"]
    assert not report["coverage"]["all_observed_tasks_certified"]


@pytest.mark.parametrize("status", ["queued", "running", "interrupted"])
def test_nonterminal_task_with_result_cannot_be_certified(status):
    report = summary([row(payload(), status)])
    assert report["certified_answers"] == 0
    assert report["failed_recovery_records"] == 1
    assert report["issue_codes"]["nonterminal_task_has_result"] == 1
    assert not report["coverage"]["all_ready_answers_recoverable"]


@pytest.mark.parametrize("bad", [None, "private row", {}, {"request_id": "private bad id"}])
def test_malformed_records_block_full_coverage_even_alongside_good_answers(bad):
    report = summary([bad, row(payload())])
    assert report["rows_observed"] == 2
    assert report["certified_answers"] == 1
    assert report["unassessed_rows"] == 1
    assert report["malformed_rows"] == 1
    assert report["status"] == "complete_with_unassessed_records"
    assert report["scan_complete"] is True
    assert report["coverage"]["assessment_complete"] is False
    assert not report["coverage"]["all_ready_answers_recoverable"]
    assert not report["coverage"]["all_observed_tasks_certified"]
    assert report["claims"]["durable_recovery_coverage"] == "unverified"
    assert "private" not in json.dumps(report)


def test_malformed_only_history_is_not_reported_as_empty():
    report = summary([None, {"request_id": "not-a-uuid"}])
    assert report["status"] == "complete_with_unassessed_records"
    assert report["unassessed_rows"] == 2
    assert report["answers_observed"] == 0
    assert not report["coverage"]["all_ready_answers_recoverable"]


@pytest.mark.parametrize("marker", [[], {}, ["2.0"], {"private": "protocol"}, "private protocol", None, 2])
def test_malformed_protocol_is_rejected_in_actual_saved_answer_recovery(marker):
    saved = payload(**{PROTOCOL_KEY: marker})
    check = verify_recovered_answer_payload(saved, expected_request_id=RID)
    assert not check["valid"]
    assert "answer_provenance_protocol_unsupported" in check["issues"]
    result = TaskStore(Client([row(saved)])).get(RID, TOKEN)
    assert result["status"] == "failed"
    assert result["result"]["error"]
    assert PRIVATE not in result["result"]["reply"]
    cert = certify_saved_answer_row(row(saved), request_id=RID, current_release={})
    assert cert["protocol_version"] == "unsupported"
    assert "private" not in json.dumps(cert)
    report = summary([row(saved), row(payload())])
    assert report["failed_recovery_records"] == 1
    assert report["certified_answers"] == 1
    assert report["unassessed_rows"] == 0


@pytest.mark.parametrize("status", ["private status content", {"private": "status content"}])
def test_invalid_task_status_is_rejected_without_echoing_it(status):
    cert = certify_saved_answer_row(row(payload(), status), request_id=RID, current_release={})
    assert cert["status"] == "failed_task_state"
    assert cert["stored_task_status"] == "invalid"
    assert "private" not in json.dumps(cert)
    assert not cert["certified"]


def test_verifier_error_blocks_claims_without_aborting_or_leaking_exception(monkeypatch):
    real = coverage.certify_saved_answer_row
    def verifier(item, **kwargs):
        if item.get("raise_fixture"):
            raise RuntimeError("private exception content")
        return real(item, **kwargs)
    monkeypatch.setattr(coverage, "certify_saved_answer_row", verifier)
    report = summary([{**row(payload()), "raise_fixture": True}, row(payload())])
    assert report["answers_observed"] == 2
    assert report["certified_answers"] == 1
    assert report["verification_error_rows"] == 1
    assert report["unassessed_rows"] == 1
    assert not report["coverage"]["all_ready_answers_recoverable"]
    assert report["issue_codes"]["recovery_verification_error"] == 1
    assert "private" not in json.dumps(report)
    assert PRIVATE not in json.dumps(report)


def test_all_failures_counted_when_findings_are_bounded():
    report = summary([row(None)] * 70)
    assert report["failed_ready_answers"] == 70
    assert len(report["failure_findings"]) == 50
    assert report["failure_findings_omitted"] == 20
    assert RID not in json.dumps(report)


def test_capped_scan_with_unassessed_rows_stays_incomplete():
    report = summary([None], scan_complete=False, capped=True)
    assert report["status"] == "incomplete_scan"
    assert report["claims"]["durable_recovery_coverage"] == "incomplete"
    assert not report["coverage"]["assessment_complete"]


class Query:
    def __init__(self, rows): self.rows = rows
    def select(self, *_): return self
    def eq(self, *_): return self
    def order(self, *_, **__): return self
    def limit(self, *_): return self
    def lte(self, *_): return self
    def range(self, *_): return self
    def execute(self): return SimpleNamespace(data=self.rows)


class Client:
    def __init__(self, rows): self.rows = rows
    def table(self, _): return Query(self.rows)


def test_endpoint_surfaces_terminal_failure_and_unassessed_records(monkeypatch):
    from api import server
    missing = row(None)
    missing["request_id"] = "00000000-0000-4000-8000-000000000112"
    monkeypatch.setattr(server.task_store, "client", Client([missing, row(payload()), None]))
    report = server.cognition_recovery_coverage_certification(
        page_size=100, max_rows=10000, x_l_recovery_token=TOKEN,
    )
    assert report["failed_ready_answers"] == 1
    assert report["unassessed_rows"] == 1
    assert report["certified_answers"] == 1
    assert report["status"] == "incomplete_scan"
    assert report["scan"]["error"] == "invalid_scan_key"
    assert not report["coverage"]["all_ready_answers_recoverable"]
    assert report["scan"]["read_only"]


def test_real_database_client_query_keeps_owner_filters_and_stable_order():
    import httpx
    from supabase import create_client
    from supabase.lib.client_options import SyncClientOptions

    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=[row(None)], request=request)
    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        client = create_client("https://example.supabase.co", "fixture-key", options=SyncClientOptions(
            httpx_client=transport, auto_refresh_token=False, persist_session=False,
        ))
        report = coverage.load_recovery_coverage_certification(client, TOKEN)
    assert not report["coverage"]["all_ready_answers_recoverable"]
    assert len(requests) == 1 and requests[0].method == "GET"
    params = requests[0].url.params
    uid, owner = owner_identity(TOKEN)
    assert params["user_id"] == "eq." + uid
    assert params["owner_hash"] == "eq." + owner
    assert params["order"] == "created_at.asc,request_id.asc"
