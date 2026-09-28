import hashlib
from pathlib import Path

from services.foundation_companion_service import list_delayed_completion_history


USER = "11111111-1111-4111-8111-111111111111"
VALID_REQUEST = "22222222-2222-4222-8222-222222222222"
BAD_REQUEST = "33333333-3333-4333-8333-333333333333"


class Result:
    def __init__(self, data):
        self.data = data


class Rpc:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return Result(self.data)


class FakeDb:
    def __init__(self, rows):
        self.rows = rows

    def rpc(self, name, params=None):
        if name == "companion_delayed_completion_history_v1":
            return Rpc({
                "status": "ok",
                "version": "1.0",
                "items": list(self.rows)[: int((params or {})["p_limit"])],
            })
        raise AssertionError(name)


def test_delayed_completion_history_returns_only_hash_verified_answers():
    answer = "Your final Vanuatu plan now includes the completed dive brief."
    answer_sha = hashlib.sha256(answer.encode()).hexdigest()
    packet_sha = hashlib.sha256(b"packet").hexdigest()

    db = FakeDb([
        {
            "requestId": VALID_REQUEST,
            "sourceConversationId": "11111111-2222-4333-8444-555555555555",
            "sourceMessageId": VALID_REQUEST,
            "requestText": "Plan Vanuatu and include diving",
            "completedAt": "2026-09-28T02:00:00Z",
            "updatedAt": "2026-09-28T02:01:00Z",
            "packetSha256": packet_sha,
            "finalAnswer": answer,
            "finalAnswerSha256": answer_sha,
            "finalAnswerGeneratedAt": "2026-09-28T02:00:30Z",
            "temporalReceipt": None,
        },
        {
            "requestId": BAD_REQUEST,
            "sourceConversationId": "11111111-2222-4333-8444-555555555555",
            "sourceMessageId": BAD_REQUEST,
            "requestText": "Tampered answer",
            "completedAt": "2026-09-28T02:00:00Z",
            "updatedAt": "2026-09-28T02:01:00Z",
            "packetSha256": packet_sha,
            "finalAnswer": "changed after hashing",
            "finalAnswerSha256": answer_sha,
            "finalAnswerGeneratedAt": "2026-09-28T02:00:30Z",
            "temporalReceipt": None,
        },
    ])

    result = list_delayed_completion_history(db, USER, limit=100)

    assert result["status"] == "ok"
    assert result["version"] == "2.0"
    assert result["returned_count"] == 1
    assert result["rejected_count"] == 1
    assert result["items"][0]["request_id"] == VALID_REQUEST
    assert result["items"][0]["final_answer"] == answer
    assert result["items"][0]["integrity"] == "verified"
    assert result["items"][0]["freshness"]["status"] == "not_tracked"
    assert result["items"][0]["completion_receipt"]["status"] == "sealed"
    assert "inputs" not in result["items"][0]


def test_delayed_history_limit_is_bounded():
    db = FakeDb([])
    for value in (0, 101, True):
        try:
            list_delayed_completion_history(db, USER, limit=value)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid history limit must fail closed")


def test_foundation_api_exposes_owner_scoped_completion_history():
    source = Path("api/foundation_companion.py").read_text(encoding="utf-8")
    assert '@router.get("/completions/history")' in source
    assert "list_delayed_completion_history" in source
    assert "owner_id(request)" in source


def test_browser_history_reverifies_answer_hash_before_saved_answer_merge():
    completions = Path("ui/concierge-completions.js").read_text(encoding="utf-8")
    index = Path("ui/index.html").read_text(encoding="utf-8")

    assert "async function delayedHistory" in completions
    assert "await window.sha256HexText(answer)" in completions
    assert "actual !== answerSha" in completions
    assert "history: (limit = 100) => delayedHistory(limit)" in completions

    assert "window.lConciergeCompletions?.history?.(100)" in index
    assert "run.delayed.set(item.requestId, item)" in index
    assert "Delayed final answer" in index
    assert "savedText = delayed.displayAnswer || delayed.finalAnswer" in index
    assert "verifyCompletionReceipt" in completions
    assert 'concierge-completions.js?v=192' in index


def test_delayed_final_answer_precedence_does_not_mutate_server_task_history():
    index = Path("ui/index.html").read_text(encoding="utf-8")
    assert "const delayed = run.delayed.get(task.requestId)" in index
    assert "savedText = delayed.displayAnswer || delayed.finalAnswer" in index
    assert "clearPendingRequest(task.requestId)" in index
    assert "Delayed final answer" in index



def test_fresh_browser_still_exposes_saved_answers_and_live_completion_clears_pending():
    index = Path("ui/index.html").read_text(encoding="utf-8")
    completions = Path("ui/concierge-completions.js").read_text(encoding="utf-8")

    tasks_lookup = index.index("async function resumePendingRequest()")
    button_lookup = index.index('button.id = \'savedAnswersAction\'', tasks_lookup)
    assert tasks_lookup < button_lookup
    assert "if (!tasks.length)" in index[tasks_lookup:button_lookup]
    assert "insertBefore(button" in index[button_lookup:button_lookup + 500]

    assert "event.sourceMessageId || event.requestId" in completions
    assert "window.clearPendingRequest(sourceMessageId)" in completions
