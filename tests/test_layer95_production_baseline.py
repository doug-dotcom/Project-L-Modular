from copy import deepcopy
from types import SimpleNamespace as NS

import pytest

from core.cognition.delivery_integrity import seal_chat_delivery_payload
from core.cognition.production_baseline import load_production_baseline, summarise_production_baseline
from core.cognition.durable_tasks import owner_identity


def row(number=1, version="14.10", fallback=False):
    request_id = f"00000000-0000-0000-0000-{number:012d}"
    payload = {"reply": "PRIVATE ANSWER", "cognition": {
        "version": version, "runtime": {"status": "degraded" if fallback else "complete", "fallback_used": fallback},
        "model_receipt": {"model_id": "test-model", "duration_ms": 100,
                          "cost": {"amount": .01, "currency": "USD", "status": "estimated_standard_text"}},
        "recall_plan": {"latency_ms": 50, "source_count": 3},
    }}
    return {"request_id": request_id, "created_at": "2026-09-23T00:00:00Z",
            "updated_at": "2026-09-23T00:00:02Z", "status": "ready",
            "request": {"message": "PRIVATE PROMPT"},
            "result": seal_chat_delivery_payload(payload, request_id=request_id)}


def test_empty_has_no_success_or_quality_score():
    report = summarise_production_baseline([])
    assert report["status"] == "no_data"
    assert report["answer_quality"]["score"] is None
    assert report["cohorts"] == []


def test_versions_separate_actual_receipts_no_private_text():
    report = summarise_production_baseline([row(), row(2, "14.9-failsafe", True)])
    assert report["tasks_observed"] == 2
    assert len(report["cohorts"]) == 2
    current = report["cohorts"][0]
    assert current["runtime"] == {"complete": 1}
    assert current["delivery_integrity"] == {"verified": 1}
    assert current["task_elapsed_ms"]["median"] == 2000
    assert current["response_model_cost"]["totals"][0]["amount"] == .01
    assert "PRIVATE" not in str(report)
    assert "00000000" not in str(report)


def test_tampering_cannot_supply_trusted_telemetry():
    data = row(version="14.9-failsafe")
    data["result"]["reply"] = "changed"
    cohort = summarise_production_baseline([data])["cohorts"][0]
    assert cohort["delivery_integrity"] == {"invalid": 1}
    assert cohort["runtime"] == {"unknown": 1}
    assert cohort["response_model_cost"]["observed"] == 0


def test_export_keeps_payload_number_types_for_hash_verification():
    import json
    from scripts.production_baseline import parse_task_export
    data = row()
    data["result"]["cognition"]["numeric_fixture"] = 0.0
    data["result"] = seal_chat_delivery_payload(data["result"], request_id=data["request_id"])
    export = {**data, "result_json": json.dumps(data["result"])}
    del export["result"]
    parsed = parse_task_export(json.dumps([export]))
    assert type(parsed[0]["result"]["cognition"]["numeric_fixture"]) is float
    assert summarise_production_baseline(parsed)["cohorts"][0]["delivery_integrity"] == {"verified": 1}


def test_invalid_numbers_are_missing_and_even_median_is_correct():
    rows = [row(1), row(2)]
    rows[1]["updated_at"] = "2026-09-23T00:00:04Z"
    rows[0]["result"]["cognition"]["model_receipt"]["duration_ms"] = True
    rows[0]["result"] = seal_chat_delivery_payload(rows[0]["result"], request_id=rows[0]["request_id"])
    cohort = summarise_production_baseline(rows)["cohorts"][0]
    assert cohort["task_elapsed_ms"]["median"] == 3000
    assert cohort["response_model_ms"]["observed"] == 1


def test_legacy_receipts_remain_unknown_not_verified():
    data = row(version="14.9-failsafe")
    data["result"] = {"reply": "legacy", "cognition": {"version": "14.9-failsafe"}}
    cohort = summarise_production_baseline([data])["cohorts"][0]
    assert cohort["runtime"] == {"legacy_fallback": 1}
    assert cohort["delivery_integrity"] == {"legacy_unbound": 1}
    assert cohort["response_model_ms"]["median"] is None
    assert cohort["response_model_cost"]["missing"] == 1


def test_pending_tasks_not_counted_as_completed_latency_and_duplicates_not_inflated():
    data = row()
    data.update(status="running", result=None)
    report = summarise_production_baseline([data, deepcopy(data), None])
    assert report["tasks_observed"] == 1
    assert report["duplicate_rows_ignored"] == 1
    assert report["malformed_rows_ignored"] == 1
    assert report["cohorts"][0]["task_elapsed_ms"]["observed"] == 0
    assert report["cohorts"][0]["delivery_integrity"] == {"no_result": 1}


def test_cost_currencies_and_bases_not_combined():
    rows = [row(i) for i in range(1, 4)]
    rows[1]["result"]["cognition"]["model_receipt"]["cost"]["currency"] = "AUD"
    rows[2]["result"]["cognition"]["model_receipt"]["cost"]["status"] = "actual"
    for data in rows:
        data["result"] = seal_chat_delivery_payload(data["result"], request_id=data["request_id"])
    costs = summarise_production_baseline(rows)["cohorts"][0]["response_model_cost"]
    assert len(costs["totals"]) == 3
    assert costs["observed"] == 3


class Database:
    def __init__(self):
        self.calls = []
    def __getattr__(self, name):
        def call(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return NS(data=[row()]) if name == "execute" else self
        return call


def test_database_read_is_bounded_and_owner_scoped():
    db = Database()
    token = "test-recovery-token-" * 3
    report = load_production_baseline(db, token, 12)
    user, digest = owner_identity(token)
    assert ("eq", ("user_id", user), {}) in db.calls
    assert ("eq", ("owner_hash", digest), {}) in db.calls
    assert ("limit", (12,), {}) in db.calls
    assert all(c[0] not in {"insert", "update", "rpc", "delete"} for c in db.calls)
    assert report["sample"]["scope"] == "recovery_token_owner"


@pytest.mark.parametrize("token,limit", [("", 10), ("x"*40, 0), ("x"*40, 101), ("x"*40, True)])
def test_bad_access_or_limit_fails_before_database(token, limit):
    db = Database()
    with pytest.raises(ValueError):
        load_production_baseline(db, token, limit)
    assert db.calls == []


def test_endpoint_uses_scoped_reader_and_sanitises_database_errors(monkeypatch):
    from api import server
    from fastapi import HTTPException
    db = Database()
    monkeypatch.setattr(server, "task_store", NS(client=db))
    result = server.cognition_baseline(10, "x"*40)
    assert result["tasks_observed"] == 1
    def broken(*args):
        raise RuntimeError("PRIVATE DATABASE ERROR")
    monkeypatch.setattr(db, "execute", broken)
    with pytest.raises(HTTPException) as err:
        server.cognition_baseline(10, "x"*40)
    assert err.value.status_code == 503
    assert "PRIVATE" not in err.value.detail
