import json

from services.concierge_retry_service import run_concierge_retry_once


USER = "11111111-1111-4111-8111-111111111111"
REQUEST = "22222222-2222-4222-8222-222222222222"
RETRY_JOB = "33333333-3333-4333-8333-333333333333"
CLAIM = "44444444-4444-4444-8444-444444444444"
LINK = "55555555-5555-4555-8555-555555555555"


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
        self.table = table
        self.mode = mode
        self.payload = payload
        self.filters = {}

    def select(self, *args):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def limit(self, value):
        return self

    def insert(self, payload):
        return Query(self.db, self.table, "insert", payload)

    def update(self, payload):
        return Query(self.db, self.table, "update", payload)

    def execute(self):
        if self.mode == "select":
            rows = [
                row.copy()
                for row in self.db.tables.get(self.table, [])
                if all(str(row.get(k)) == str(v) for k, v in self.filters.items())
            ]
            return Result(rows)
        if self.mode == "insert":
            self.db.tables.setdefault(self.table, []).append(self.payload.copy())
            return Result([self.payload.copy()])
        if self.mode == "update":
            changed = []
            for row in self.db.tables.get(self.table, []):
                if all(str(row.get(k)) == str(v) for k, v in self.filters.items()):
                    row.update(self.payload)
                    changed.append(row.copy())
            return Result(changed)
        raise AssertionError(self.mode)


class FakeDb:
    def __init__(self):
        self.tables = {
            "companion_foundation_pending_jobs": [{
                "job_id": REQUEST,
                "user_id": USER,
                "link_request_id": LINK,
                "purpose": "concierge.cross-project-read",
                "capability_ids": [
                    "travel.plan_trip",
                    "dive.destination_brief",
                ],
                "inputs": {
                    "travel.plan_trip": {"destination": "Vanuatu"},
                    "dive.destination_brief": {"destination": "Vanuatu"},
                },
                "source_conversation_id": "doug_primary",
                "source_message_id": REQUEST,
                "status": "ready",
            }],
            "companion_concierge_completion_outbox": [],
        }

    def table(self, name):
        return Query(self, name)

    def rpc(self, name, params=None):
        if name == "concierge_foundation_client_token_v1":
            return Rpc("c" * 128)
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
        raise AssertionError(name)


class Response:
    def __init__(self, code, payload):
        self.status_code = code
        self.payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {"content-length": str(len(self.content))}

    def json(self):
        return self.payload


def claim_payload(capabilities=None):
    return {
        "status": "ok",
        "reasonCode": "retry-claimed",
        "retry": {
            "claimed": True,
            "retryJobId": RETRY_JOB,
            "requestId": REQUEST,
            "ownerShineId": USER,
            "clientId": "shine.companion",
            "capabilityIds": capabilities or ["dive.destination_brief"],
            "attempt": 1,
            "maxAttempts": 4,
            "claimToken": CLAIM,
            "expiresAt": "2026-09-29T00:00:00Z",
        },
    }


def test_resume_reuses_completed_checkpoint_and_finishes_retry():
    calls = []

    def post(url, *, json, headers, **kwargs):
        calls.append((url, json, headers))
        if url.endswith("/retry/claim"):
            return Response(200, claim_payload())
        if url.endswith("/concierge/resume"):
            assert json["requestId"] == REQUEST
            assert json["inputs"] == {
                "dive.destination_brief": {"destination": "Vanuatu"}
            }
            return Response(200, {
                "status": "completed",
                "reasonCode": "concierge-execution-completed",
                "results": [
                    {
                        "capabilityId": "travel.plan_trip",
                        "status": "completed",
                        "reasonCode": "concierge-step-reused",
                        "result": {"summary": "Trip"},
                        "reused": True,
                    },
                    {
                        "capabilityId": "dive.destination_brief",
                        "status": "completed",
                        "reasonCode": "capability-completed",
                        "result": {"summary": "Dive"},
                    },
                ],
                "synthesisReady": True,
                "synthesisMustDisclosePartial": False,
            })
        if url.endswith("/retry/finish"):
            assert json["outcome"] == "completed"
            return Response(200, {
                "status": "ok",
                "reasonCode": "retry-finished",
                "retry": {"status": "completed", "retryJobId": RETRY_JOB},
            })
        raise AssertionError(url)

    db = FakeDb()
    result = run_concierge_retry_once(db, post_impl=post)
    assert result["status"] == "completed"
    assert result["reused_count"] == 1
    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "completed"
    outbox = db.tables["companion_concierge_completion_outbox"]
    assert len(outbox) == 1
    assert outbox[0]["event_type"] == "retry-completed"


def test_partial_resume_closes_old_claim_because_foundation_already_requeues():
    finishes = []

    def post(url, *, json, **kwargs):
        if url.endswith("/retry/claim"):
            return Response(200, claim_payload())
        if url.endswith("/concierge/resume"):
            return Response(200, {
                "status": "partial",
                "reasonCode": "concierge-execution-partial",
                "results": [],
                "retry": {"queued": True},
                "synthesisReady": True,
                "synthesisMustDisclosePartial": True,
            })
        if url.endswith("/retry/finish"):
            finishes.append(json["outcome"])
            return Response(200, {
                "status": "ok",
                "reasonCode": "retry-finished",
                "retry": {"status": "completed"},
            })
        raise AssertionError(url)

    db = FakeDb()
    result = run_concierge_retry_once(db, post_impl=post)
    assert result["status"] == "partial"
    assert result["next_retry_scheduled"] is True
    assert finishes == ["completed"]
    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "ready"


def test_network_uncertainty_requeues_claim_and_keeps_local_context():
    outcomes = []

    def post(url, *, json, **kwargs):
        if url.endswith("/retry/claim"):
            return Response(200, claim_payload())
        if url.endswith("/concierge/resume"):
            raise RuntimeError("connection lost")
        if url.endswith("/retry/finish"):
            outcomes.append(json["outcome"])
            return Response(200, {
                "status": "ok",
                "reasonCode": "retry-finished",
                "retry": {"status": "requeued"},
            })
        raise AssertionError(url)

    db = FakeDb()
    result = run_concierge_retry_once(db, post_impl=post)
    assert result["status"] == "retry"
    assert outcomes == ["retry"]
    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "ready"


def test_missing_local_context_is_abandoned_never_reconstructed():
    outcomes = []

    def post(url, *, json, **kwargs):
        if url.endswith("/retry/claim"):
            return Response(200, claim_payload())
        if url.endswith("/retry/finish"):
            outcomes.append(json["outcome"])
            return Response(200, {
                "status": "ok",
                "reasonCode": "retry-finished",
                "retry": {"status": "abandoned"},
            })
        raise AssertionError(url)

    db = FakeDb()
    db.tables["companion_foundation_pending_jobs"] = []
    result = run_concierge_retry_once(db, post_impl=post)
    assert result["status"] == "abandoned"
    assert result["reason_code"] == "companion-retry-context-missing"
    assert outcomes == ["abandoned"]


def test_terminal_resume_failure_marks_local_failed_and_emits_abandoned_event():
    def post(url, *, json, **kwargs):
        if url.endswith("/retry/claim"):
            return Response(200, claim_payload())
        if url.endswith("/concierge/resume"):
            return Response(409, {
                "status": "blocked",
                "reasonCode": "integration-grant-inactive",
            })
        if url.endswith("/retry/finish"):
            assert json["outcome"] == "abandoned"
            return Response(200, {
                "status": "ok",
                "reasonCode": "retry-finished",
                "retry": {"status": "abandoned"},
            })
        raise AssertionError(url)

    db = FakeDb()
    result = run_concierge_retry_once(db, post_impl=post)
    assert result["status"] == "abandoned"
    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "failed"
    outbox = db.tables["companion_concierge_completion_outbox"]
    assert outbox[0]["event_type"] == "retry-abandoned"



def test_partial_without_new_foundation_retry_requeues_old_claim():
    finishes = []

    def post(url, *, json, **kwargs):
        if url.endswith("/retry/claim"):
            return Response(200, claim_payload())
        if url.endswith("/concierge/resume"):
            return Response(200, {
                "status": "partial",
                "reasonCode": "concierge-execution-partial",
                "results": [],
                "synthesisReady": True,
                "synthesisMustDisclosePartial": True,
            })
        if url.endswith("/retry/finish"):
            finishes.append(json["outcome"])
            return Response(200, {
                "status": "ok",
                "reasonCode": "retry-finished",
                "retry": {"status": "requeued"},
            })
        raise AssertionError(url)

    db = FakeDb()
    result = run_concierge_retry_once(db, post_impl=post)
    assert result["status"] == "partial"
    assert finishes == ["retry"]
    assert result["next_retry_scheduled"] is True
    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "ready"


def test_server_lifecycle_starts_and_stops_retry_runner():
    from pathlib import Path

    source = Path("api/server.py").read_text(encoding="utf-8")
    assert "ConciergeRetryRunner" in source
    assert "concierge_retry_runner.start()" in source
    assert "concierge_retry_runner.stop()" in source
    assert "source_conversation_id=conversation_scope" in source
    assert "source_message_id=request_id" in source


def test_foundation_api_exposes_leased_completion_claim_and_ack():
    from pathlib import Path

    source = Path("api/foundation_companion.py").read_text(encoding="utf-8")
    assert '@router.post("/completions/claim")' in source
    assert '@router.post("/completions/{event_id}/ack")' in source
    assert "companion_claim_completion_event_v2" in source
    assert "companion_ack_completion_event_v2" in source
