import hashlib
import json
from pathlib import Path

import pytest

from services.foundation_companion_service import (
    claim_delayed_completion,
    list_delayed_completion_history,
)
from services.concierge_completion_synthesis import (
    synthesise_delayed_concierge_completion,
)


USER = "11111111-1111-4111-8111-111111111111"
REQUEST = "22222222-2222-4222-8222-222222222222"
EVENT = "33333333-3333-4333-8333-333333333333"
LEASE = "44444444-4444-4444-8444-444444444444"
CONVERSATION = "55555555-5555-4555-8555-555555555555"
ANSWER = "The delayed Vanuatu result is now complete."
ANSWER_SHA = hashlib.sha256(ANSWER.encode()).hexdigest()
PACKET_SHA = hashlib.sha256(b"specialist-packet").hexdigest()
GENERATED = "2026-09-28T03:20:00Z"


class Result:
    def __init__(self, data):
        self.data = data


class Rpc:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return Result(self.data)


class FakeDb:
    def __init__(self, *, mismatch=False, freshness="unchanged"):
        self.mismatch = mismatch
        self.freshness = freshness
        self.calls = []

    def rpc(self, name, params=None):
        self.calls.append((name, params or {}))
        if name == "companion_claim_completion_event_v3":
            return Rpc({
                "available": True,
                "eventId": EVENT,
                "leaseToken": LEASE,
                "eventType": "retry-completed",
                "requestId": REQUEST,
                "sourceConversationId": (
                    "66666666-6666-4666-8666-666666666666"
                    if self.mismatch else CONVERSATION
                ),
                "sourceMessageId": REQUEST,
                "finalAnswer": ANSWER,
                "finalAnswerSha256": ANSWER_SHA,
                "finalAnswerGeneratedAt": GENERATED,
                "resultPacketSha256": PACKET_SHA,
                "synthesisStatus": "ready",
            })
        if name == "companion_delayed_synthesis_state_v1":
            return Rpc({
                "found": True,
                "requestId": REQUEST,
                "temporalReceipt": {
                    "status": "checked",
                    "user_id": USER,
                    "dependencies": [{"subject": "trip", "predicate": "status", "revision": 1}],
                    "terms": ["vanuatu"],
                },
            })
        if name == "l_fact_freshness":
            return Rpc({"status": self.freshness})
        if name == "companion_delayed_completion_history_v1":
            return Rpc({
                "status": "ok",
                "version": "1.0",
                "items": [{
                    "requestId": REQUEST,
                    "sourceConversationId": CONVERSATION,
                    "sourceMessageId": REQUEST,
                    "requestText": "Plan Vanuatu and include diving",
                    "completedAt": "2026-09-28T03:21:00Z",
                    "updatedAt": "2026-09-28T03:21:00Z",
                    "packetSha256": PACKET_SHA,
                    "finalAnswer": ANSWER,
                    "finalAnswerSha256": ANSWER_SHA,
                    "finalAnswerGeneratedAt": GENERATED,
                    "temporalReceipt": {
                        "status": "checked",
                        "user_id": USER,
                        "dependencies": [],
                        "terms": ["vanuatu"],
                    },
                }],
            })
        raise AssertionError(name)


def canonical_receipt_hash(receipt):
    body = {key: receipt[key] for key in sorted(receipt) if key != "receipt_sha256"}
    return hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def test_live_completion_is_conversation_bound_and_receipt_sealed():
    db = FakeDb()
    result = claim_delayed_completion(
        db,
        USER,
        source_conversation_id=CONVERSATION,
    )

    claim_call = next(call for call in db.calls if call[0] == "companion_claim_completion_event_v3")
    assert claim_call[1]["p_source_conversation_id"] == CONVERSATION
    assert result["sourceConversationId"] == CONVERSATION
    assert result["freshness"]["status"] == "unchanged"
    assert result["freshness"]["tracking"] == "temporal_dependencies"

    receipt = result["completionReceipt"]
    assert receipt["request_id"] == REQUEST
    assert receipt["source_conversation_id"] == CONVERSATION
    assert receipt["answer_generated_at"] == GENERATED
    assert receipt["final_answer_sha256"] == ANSWER_SHA
    assert receipt["result_packet_sha256"] == PACKET_SHA
    assert receipt["receipt_sha256"] == canonical_receipt_hash(receipt)


def test_conversation_mismatch_fails_closed():
    with pytest.raises(RuntimeError, match="completion-conversation-binding-mismatch"):
        claim_delayed_completion(
            FakeDb(mismatch=True),
            USER,
            source_conversation_id=CONVERSATION,
        )


def test_history_preserves_answer_but_refreshes_freshness_annotation():
    stale = list_delayed_completion_history(
        FakeDb(freshness="superseded"),
        USER,
        limit=100,
    )
    current = list_delayed_completion_history(
        FakeDb(freshness="unchanged"),
        USER,
        limit=100,
    )

    assert stale["items"][0]["final_answer"] == current["items"][0]["final_answer"] == ANSWER
    assert stale["items"][0]["completion_receipt"] == current["items"][0]["completion_receipt"]
    assert stale["items"][0]["freshness"]["status"] == "superseded"
    assert current["items"][0]["freshness"]["status"] == "unchanged"


def test_browser_chat_sends_stable_conversation_and_completion_claim_filters_it():
    index = Path("ui/index.html").read_text(encoding="utf-8")
    completions = Path("ui/concierge-completions.js").read_text(encoding="utf-8")

    assert 'const CONVERSATION_KEY = "project-l-conversation-id-v1"' in index
    assert "function currentConversationId()" in index
    assert "conversation_id: currentConversationId()" in index
    assert "conversationId, pending: true" in index
    assert "window.currentConversationId = currentConversationId" in index

    assert "body: JSON.stringify({conversation_id: conversationId})" in completions
    assert "sourceConversationId !== expectedConversationId" in completions
    assert "verifyCompletionReceipt" in completions
    assert "pointInTimeText" in completions
    assert "Relevant tracked facts have since changed" in completions


def test_server_rejects_invalid_supplied_conversation_id():
    source = Path("api/server.py").read_text(encoding="utf-8")
    assert "def normalise_conversation_id(value):" in source
    assert 'raise HTTPException(400, "A valid conversation ID is required")' in source


def test_saved_answers_marks_superseded_delayed_result_for_attention():
    source = Path("ui/index.html").read_text(encoding="utf-8")
    assert "Delayed answer · facts changed" in source
    assert "delayed.displayAnswer || delayed.finalAnswer" in source
    assert "['superseded', 'unavailable'].includes(delayedFreshness)" in source



class SynthesisAdapter:
    available = True
    provider = "fixture"
    model_id = "fixture-model"

    def generate(self, request):
        return {
            "status": "complete",
            "content": "Final delayed answer",
            "provider": self.provider,
            "model_id": self.model_id,
        }


def test_delayed_synthesiser_emits_temporal_receipt_and_generation_time():
    temporal = {
        "status": "checked",
        "user_id": USER,
        "dependencies": [],
        "terms": ["vanuatu"],
    }

    def cognitive_runner(
        message,
        rhee_packet,
        capability_packet=None,
        client=None,
        model=None,
        cognitive_plan=None,
        model_adapter=None,
    ):
        return {
            "version": "fixture",
            "runtime": {"status": "ok"},
            "controller": cognitive_plan,
            "route": {},
            "guardrails": {"passed": True, "issues": []},
        }

    result = synthesise_delayed_concierge_completion(
        "Plan Vanuatu and include diving",
        {
            "status": "completed",
            "reason_code": "done",
            "results": [],
            "synthesis_ready": True,
        },
        model_adapter=SynthesisAdapter(),
        rhee_builder=lambda _message: {
            "context": "Relevant context",
            "recall_active": True,
            "deep_recall": False,
            "temporal_memory": temporal,
        },
        cognition_planner=lambda _message: {
            "difficulty": "medium",
            "needs": {
                "memory": True,
                "structured_reasoning": False,
                "longitudinal_reasoning": False,
                "specialist": True,
                "action": False,
            },
        },
        cognitive_runner=cognitive_runner,
    )

    assert result["status"] == "ready"
    assert result["temporal_receipt"] == temporal
    assert result["generated_at"].endswith("Z")
