import json

from services.concierge_retry_service import run_concierge_retry_once


USER = "11111111-1111-4111-8111-111111111111"
REQUEST = "22222222-2222-4222-8222-222222222222"
RETRY_JOB = "33333333-3333-4333-8333-333333333333"
CLAIM = "44444444-4444-4444-8444-444444444444"
LINK = "55555555-5555-4555-8555-555555555555"
NEXT_RETRY = "66666666-6666-4666-8666-666666666666"


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
                "request_text": "Plan Vanuatu and include diving",
                "status": "ready",
                "synthesis_status": "not-required",
                "final_result_sha256": None,
                "final_answer": None,
                "final_answer_sha256": None,
                "final_answer_generated_at": None,
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
        if name == "companion_store_delayed_synthesis_packet_v1":
            row = self.tables["companion_foundation_pending_jobs"][0]
            packet = (params or {})["p_packet"]
            digest = (params or {})["p_packet_sha256"]
            existing = getattr(self, "synthesis_packet", None)
            if existing is not None and existing != packet:
                raise AssertionError("synthesis packet conflict")
            self.synthesis_packet = packet
            row["final_result_sha256"] = digest
            if row.get("synthesis_status") != "ready":
                row["synthesis_status"] = "pending"
                row["final_answer"] = None
                row["final_answer_sha256"] = None
            return Rpc({
                "stored": True,
                "replayed": row.get("synthesis_status") == "ready",
                "packetSha256": digest,
                "synthesisStatus": row.get("synthesis_status"),
            })
        if name == "companion_delayed_synthesis_state_v1":
            row = self.tables["companion_foundation_pending_jobs"][0]
            return Rpc({
                "found": True,
                "requestId": row["job_id"],
                "requestText": row.get("request_text"),
                "synthesisStatus": row.get("synthesis_status"),
                "packetSha256": row.get("final_result_sha256"),
                "resultPacket": getattr(self, "synthesis_packet", None),
                "finalAnswer": row.get("final_answer"),
                "finalAnswerSha256": row.get("final_answer_sha256"),
                "finalAnswerGeneratedAt": row.get("final_answer_generated_at"),
                "temporalReceipt": getattr(self, "temporal_receipt", None),
            })
        if name == "companion_store_delayed_synthesis_answer_v2":
            row = self.tables["companion_foundation_pending_jobs"][0]
            row["final_answer"] = (params or {})["p_answer"]
            row["final_answer_sha256"] = (params or {})["p_answer_sha256"]
            row["final_answer_generated_at"] = (params or {})["p_generated_at"]
            self.temporal_receipt = (params or {}).get("p_temporal_receipt")
            row["synthesis_status"] = "ready"
            return Rpc({
                "stored": True,
                "replayed": False,
                "answerSha256": row["final_answer_sha256"],
                "synthesisStatus": "ready",
                "generatedAt": row["final_answer_generated_at"],
            })
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
    result = run_concierge_retry_once(
        db,
        post_impl=post,
        synthesise=lambda request, packet: {
            "status": "ready",
            "reply": "Your final Vanuatu plan now includes the completed dive brief.",
        },
    )
    assert result["status"] == "completed"
    assert result["reused_count"] == 1
    row = db.tables["companion_foundation_pending_jobs"][0]
    assert row["status"] == "completed"
    assert row["synthesis_status"] == "ready"
    assert row["final_answer"].startswith("Your final Vanuatu plan")
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
                "retry": {
                    "queued": True,
                    "retryJobId": NEXT_RETRY,
                },
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
    assert "request_text=user_message" in source
    assert "synthesise_delayed_concierge_completion" in source
    assert "synthesise=lambda original_request, result_packet" in source


def test_foundation_api_exposes_leased_completion_claim_and_ack():
    from pathlib import Path

    source = Path("api/foundation_companion.py").read_text(encoding="utf-8")
    assert '@router.post("/completions/claim")' in source
    assert '@router.post("/completions/{event_id}/ack")' in source
    assert "companion_claim_completion_event_v2" in source
    assert "companion_ack_completion_event_v2" in source



def test_retry_already_pending_is_current_claim_not_a_new_attempt():
    outcomes = []

    def post(url, *, json, **kwargs):
        if url.endswith("/retry/claim"):
            return Response(200, claim_payload())
        if url.endswith("/concierge/resume"):
            return Response(200, {
                "status": "partial",
                "reasonCode": "concierge-execution-partial",
                "results": [],
                "retry": {
                    "queued": False,
                    "reasonCode": "retry-already-pending",
                    "retryJobId": RETRY_JOB,
                },
                "synthesisReady": True,
                "synthesisMustDisclosePartial": True,
            })
        if url.endswith("/retry/finish"):
            outcomes.append(json["outcome"])
            return Response(200, {
                "status": "ok",
                "reasonCode": "retry-finished",
                "retry": {
                    "status": "requeued",
                    "retryJobId": NEXT_RETRY,
                },
            })
        raise AssertionError(url)

    db = FakeDb()
    result = run_concierge_retry_once(db, post_impl=post)
    assert result["status"] == "partial"
    assert outcomes == ["retry"]
    assert result["next_retry_scheduled"] is True
    assert db.tables["companion_foundation_pending_jobs"][0]["status"] == "ready"


def test_claim_transport_accepts_foundation_legacy_batch_up_to_twenty():
    from services.concierge_retry_service import claim_foundation_retry

    capabilities = [f"legacy.capability_{index}" for index in range(1, 21)]

    def post(url, **kwargs):
        assert url.endswith("/retry/claim")
        return Response(200, claim_payload(capabilities))

    result = claim_foundation_retry(FakeDb(), post_impl=post)
    assert result["status"] == "claimed"
    assert result["capability_ids"] == capabilities



def test_completed_specialists_hold_retry_lease_until_l_answer_is_ready():
    finish_calls = []

    def post(url, *, json, **kwargs):
        if url.endswith("/retry/claim"):
            return Response(200, claim_payload())
        if url.endswith("/concierge/resume"):
            return Response(200, {
                "status": "completed",
                "reasonCode": "concierge-execution-completed",
                "results": [{
                    "capabilityId": "dive.destination_brief",
                    "status": "completed",
                    "reasonCode": "capability-completed",
                    "result": {"summary": "Dive complete"},
                }],
                "synthesisReady": True,
                "synthesisMustDisclosePartial": False,
            })
        if url.endswith("/retry/finish"):
            finish_calls.append(json)
            return Response(200, {
                "status": "ok",
                "reasonCode": "retry-finished",
            })
        raise AssertionError(url)

    db = FakeDb()
    result = run_concierge_retry_once(
        db,
        post_impl=post,
        synthesise=lambda request, packet: {
            "status": "unavailable",
            "reason_code": "model-temporarily-unavailable",
        },
    )
    assert result["status"] == "synthesis-retry"
    assert finish_calls == []
    assert db.tables["companion_concierge_completion_outbox"] == []
    row = db.tables["companion_foundation_pending_jobs"][0]
    assert row["status"] == "ready"
    assert row["synthesis_status"] == "pending"
    assert row["final_result_sha256"]


def test_reclaimed_completed_retry_reuses_saved_final_answer_without_model_call():
    finish_calls = []

    def post(url, *, json, **kwargs):
        if url.endswith("/retry/claim"):
            return Response(200, claim_payload())
        if url.endswith("/concierge/resume"):
            return Response(200, {
                "status": "completed",
                "reasonCode": "concierge-execution-completed",
                "results": [{
                    "capabilityId": "dive.destination_brief",
                    "status": "completed",
                    "reasonCode": "concierge-step-reused",
                    "result": {"summary": "Dive complete"},
                    "reused": True,
                }],
                "synthesisReady": True,
                "synthesisMustDisclosePartial": False,
            })
        if url.endswith("/retry/finish"):
            finish_calls.append(json["outcome"])
            return Response(200, {
                "status": "ok",
                "reasonCode": "retry-finished",
                "retry": {"status": "completed"},
            })
        raise AssertionError(url)

    db = FakeDb()
    db.synthesis_packet = {
        "version": "shine-concierge-delayed-result/v1",
        "request_id": REQUEST,
        "status": "completed",
        "reason_code": "concierge-execution-completed",
        "capability_ids": ["dive.destination_brief"],
        "results": [{
            "capabilityId": "dive.destination_brief",
            "status": "completed",
            "reasonCode": "concierge-step-reused",
            "result": {"summary": "Dive complete"},
            "reused": True,
        }],
        "synthesis_ready": True,
        "synthesis_must_disclose_partial": False,
    }
    row = db.tables["companion_foundation_pending_jobs"][0]
    import hashlib
    encoded = json.dumps(
        db.synthesis_packet,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    row["final_result_sha256"] = hashlib.sha256(encoded).hexdigest()
    row["final_answer"] = "Saved final answer"
    row["final_answer_sha256"] = hashlib.sha256(
        row["final_answer"].encode()
    ).hexdigest()
    row["synthesis_status"] = "ready"
    row["status"] = "completed"

    def forbidden_synthesis(*args, **kwargs):
        raise AssertionError("model must not run twice")

    result = run_concierge_retry_once(
        db,
        post_impl=post,
        synthesise=forbidden_synthesis,
    )
    assert result["status"] == "completed"
    assert result["synthesis_replayed"] is True
    assert finish_calls == ["completed"]
    assert len(db.tables["companion_concierge_completion_outbox"]) == 1



def test_cancelled_job_abandons_claim_without_resuming_specialists():
    outcomes = []

    def post(url, *, json, **kwargs):
        if url.endswith("/retry/claim"):
            return Response(200, claim_payload())
        if url.endswith("/retry/finish"):
            outcomes.append((json["outcome"], json["reasonCode"]))
            return Response(200, {
                "status": "ok",
                "reasonCode": "retry-finished",
                "retry": {"status": "abandoned"},
            })
        if url.endswith("/concierge/resume"):
            raise AssertionError("cancelled job must never resume specialists")
        raise AssertionError(url)

    db = FakeDb()
    row = db.tables["companion_foundation_pending_jobs"][0]
    row["status"] = "cancelled"
    row["cancellation_reason"] = "user-cancelled"
    row["superseded_by_request_id"] = None
    row["cancelled_at"] = "2026-09-28T04:00:00Z"

    result = run_concierge_retry_once(db, post_impl=post)
    assert result["status"] == "cancelled"
    assert result["reason_code"] == "user-cancelled"
    assert outcomes == [("abandoned", "user-cancelled")]
    assert db.tables["companion_concierge_completion_outbox"] == []
