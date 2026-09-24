"""A valid saved answer and a valid task journal are both required for readiness."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import httpx
import pytest
from supabase import create_client
from supabase.lib.client_options import SyncClientOptions

from core.cognition.delivery_integrity import seal_chat_delivery_payload
from core.cognition.durable_tasks import owner_identity, request_hash
from core.cognition.recovery_coverage_certification import (
    load_recovery_coverage_certification, summarise_recovery_coverage,
)
from core.cognition.recovery_readiness import load_recovery_readiness, summarise_recovery_readiness
from core.cognition.release_provenance import build_release_provenance
from tests.test_layer110_recovery_coverage_certification import (
    KEY, KEY_ID, REPLY, env, install, key_env_name, result, rid,
)


TOKEN = "layer114-fixture-owner-no-production-access" * 2
NOW = datetime(2026, 9, 24, 2, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def fixture_keyring(monkeypatch):
    install(monkeypatch, env())


def task(n, status="ready"):
    request = {"request_id": rid(n), "message": "private fixture request"}
    row = {
        "request_id": rid(n), "owner_hash": owner_identity(TOKEN)[1],
        "input_hash": request_hash(request), "request": request,
        "status": status, "checkpoint": status, "worker_id": None,
        "lease_until": None, "result": result(rid(n)) if status in {"ready", "failed"} else None,
        "created_at": "2026-09-24T00:00:00Z", "updated_at": "2026-09-24T00:01:00Z",
    }
    if status in {"running", "interrupted"}:
        row["worker_id"] = rid(999)
        row["checkpoint"] = "generating"
        row["lease_until"] = (NOW + timedelta(minutes=1 if status == "running" else -1)).isoformat()
    return row


def summarise(rows, **kwargs):
    return summarise_recovery_readiness(
        rows, scan_complete=kwargs.get("scan_complete", True), capped=kwargs.get("capped", False),
        current_release=build_release_provenance(env()), now=NOW,
    )


def test_readiness_requires_valid_ledger_and_authenticated_saved_result():
    rows = [task(1), task(2)]
    before = deepcopy(rows)
    report = summarise(rows)
    assert report["status"] == "ready"
    assert report["recovery_ready"] is True
    assert all(report["checks"].values())
    assert not any(report["actions"].values())
    assert report["task_ledger"]["tasks_observed"] == report["saved_answers"]["answers_observed"] == 2
    assert rows == before


def test_intact_answer_does_not_hide_corrupt_task_journal():
    row = task(3)
    row["request"]["message"] = "changed request without updating hash"
    report = summarise([row])
    assert report["status"] == "needs_attention"
    assert report["recovery_ready"] is False
    assert report["checks"]["all_ready_answers_recoverable"] is True
    assert report["checks"]["ledger_consistent"] is False
    assert report["task_ledger"]["issue_codes"]["request_hash_mismatch"] == 1


def test_valid_journal_does_not_hide_tampered_saved_answer():
    row = task(4)
    row["result"]["reply"] = "private changed answer"
    report = summarise([row])
    assert report["status"] == "needs_attention"
    assert report["checks"]["ledger_consistent"] is True
    assert report["checks"]["all_ready_answers_recoverable"] is False
    assert report["saved_answers"]["failed_ready_answers"] == 1


@pytest.mark.parametrize("status", ["ready", "failed"])
@pytest.mark.parametrize("payload", [None, [], "private malformed result"])
def test_terminal_missing_result_is_a_failure_not_a_pending_task(status, payload):
    row = task(5, status)
    row["result"] = payload
    report = summarise([row])
    saved = report["saved_answers"]
    assert report["status"] == "needs_attention"
    assert saved["status"] == "complete_with_recovery_failures"
    assert saved["failed_ready_answers"] == 1
    assert saved["not_ready_answers"] == 0
    assert saved["recovery_statuses"] == {"failed_missing_result": 1}
    assert saved["coverage"]["all_ready_answers_recoverable"] is False
    assert saved["coverage"]["all_observed_tasks_certified"] is False
    assert "private" not in json.dumps(report)


@pytest.mark.parametrize("bad_row", [None, {}, {"request_id": "private bad identifier"}])
@pytest.mark.parametrize("include_valid", [False, True])
def test_malformed_rows_prevent_all_recoverable_claims(bad_row, include_valid):
    rows = ([task(6)] if include_valid else []) + [bad_row]
    saved = summarise_recovery_coverage(rows, scan_complete=True, capped=False)
    assert saved["status"] == "complete_with_malformed_records"
    assert saved["malformed_rows_ignored"] == 1
    assert saved["coverage"]["all_ready_answers_recoverable"] is False
    assert saved["coverage"]["all_observed_tasks_certified"] is False
    report = summarise(rows)
    assert report["status"] == "needs_attention"
    assert report["recovery_ready"] is False
    assert "private" not in json.dumps(report)


@pytest.mark.parametrize("status", ["queued", "running", "interrupted"])
def test_unfinished_tasks_are_explicit_and_are_never_resumed(status):
    report = summarise([task(7), task(8, status)])
    assert report["status"] == "pending_tasks"
    assert report["recovery_ready"] is False
    assert report["checks"]["ledger_consistent"] is True
    assert report["saved_answers"]["not_ready_answers"] == 1
    assert report["saved_answers"]["failed_ready_answers"] == 0
    assert not any(report["actions"].values())


def test_empty_history_is_not_presented_as_demonstrated_readiness():
    report = summarise([])
    assert report["status"] == "no_tasks"
    assert report["recovery_ready"] is False
    assert report["checks"]["all_observed_answers_modernly_authenticated"] is False


def test_legacy_readability_stays_distinct_from_modern_authentication():
    row = task(9)
    row["result"] = seal_chat_delivery_payload({"reply": "private old answer"}, request_id=rid(9))
    report = summarise([row])
    assert report["status"] == "ready_with_legacy"
    assert report["recovery_ready"] is True
    assert report["checks"]["all_observed_answers_modernly_authenticated"] is False
    assert report["saved_answers"]["legacy_readable_answers"] == 1


def test_missing_historical_verification_key_blocks_readiness(monkeypatch):
    row = task(10)
    monkeypatch.delenv(key_env_name(KEY_ID))
    report = summarise([row])
    assert report["status"] == "needs_attention"
    assert report["recovery_ready"] is False
    assert report["saved_answers"]["certified_answers"] == 0


@pytest.mark.parametrize("complete,capped", [(False, False), (False, True), (True, True)])
def test_incomplete_scan_cannot_certify_good_observations(complete, capped):
    report = summarise([task(11)], scan_complete=complete, capped=capped)
    assert report["status"] == "incomplete_scan"
    assert report["recovery_ready"] is False
    assert report["checks"]["all_observed_answers_modernly_authenticated"] is False


def test_readiness_does_not_claim_a_failed_task_was_successful():
    report = summarise([task(12, "failed")])
    assert report["recovery_ready"] is True
    assert report["claims"]["task_success"] == "not_asserted"
    assert report["task_ledger"]["task_statuses"] == {"failed": 1}


def test_failure_findings_are_bounded_without_losing_failure_count():
    rows = []
    for i in range(60):
        row = task(100 + i)
        row["result"] = None
        rows.append(row)
    report = summarise(rows)
    assert report["saved_answers"]["failed_ready_answers"] == 60
    assert len(report["saved_answers"]["failure_findings"]) == 50
    assert report["saved_answers"]["failure_findings_omitted"] == 10


@pytest.mark.parametrize("loader", [load_recovery_readiness, load_recovery_coverage_certification])
def test_real_client_uses_one_owner_scoped_keyset_scan(loader):
    requests = []
    rows = [task(20), task(21), task(22)]
    def respond(request):
        requests.append(request)
        assert len(requests) <= 2  # A second independent scan would fail here.
        params = request.url.params
        user_id, owner_hash = owner_identity(TOKEN)
        assert request.method == "GET"
        assert params["user_id"] == "eq." + user_id
        assert params["owner_hash"] == "eq." + owner_hash
        assert params["order"] == "created_at.asc,request_id.asc"
        assert "offset" not in params and "limit" in params
        assert params["created_at"].startswith("lte.")
        if len(requests) == 2:
            assert rid(21) in params["or"]
            assert params["created_at"] == requests[0].url.params["created_at"]
        return httpx.Response(200, json=rows[:2] if len(requests) == 1 else rows[2:], request=request)
    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        client = create_client("https://example.supabase.co", "fixture-key", options=SyncClientOptions(
            httpx_client=transport, auto_refresh_token=False, persist_session=False,
        ))
        report = loader(client, TOKEN, page_size=2)
    assert len(requests) == 2
    assert report["scan"]["rows_read"] == 3
    assert report["scan_complete"] is True
    if loader is load_recovery_readiness:
        assert report["recovery_ready"] is True
        assert report["task_ledger"]["tasks_observed"] == report["saved_answers"]["answers_observed"] == 3
    encoded = json.dumps(report)
    for private in (TOKEN, KEY, REPLY, "private fixture request", rows[0]["owner_hash"], rid(20)):
        assert private not in encoded


def test_http_route_requires_account_and_valid_owner_token(monkeypatch):
    from fastapi.testclient import TestClient
    from api import server
    from types import SimpleNamespace

    calls = []
    class Query:
        def select(self, *_): return self
        def eq(self, *_): return self
        def lte(self, *_): return self
        def order(self, *_, **__): return self
        def limit(self, *_): return self
        def execute(self): calls.append("GET"); return SimpleNamespace(data=[task(30)])
    monkeypatch.setattr(server.task_store, "client", SimpleNamespace(table=lambda _: Query()))
    client = TestClient(server.app)  # Do not start the task workers.
    assert client.get("/cognition/recovery-readiness").status_code == 401
    assert not calls
    monkeypatch.setattr(server, "require_account", lambda *_: {"id": "fixture-account"})
    assert client.get("/cognition/recovery-readiness").status_code == 400
    assert not calls
    response = client.get("/cognition/recovery-readiness", headers={"x-l-recovery-token": TOKEN})
    assert response.status_code == 200
    assert response.json()["recovery_ready"] is True
    assert response.headers["cache-control"] == "no-store"
    assert calls == ["GET"]


def test_database_failure_is_reported_without_backend_details(monkeypatch):
    from api import server
    from fastapi import HTTPException
    from types import SimpleNamespace

    def broken_table(_):
        raise RuntimeError("private connection details")
    monkeypatch.setattr(server.task_store, "client", SimpleNamespace(table=broken_table))
    with pytest.raises(HTTPException) as exc:
        server.cognition_recovery_readiness(page_size=100, max_rows=10000, x_l_recovery_token=TOKEN)
    assert exc.value.status_code == 503
    assert "private" not in exc.value.detail
