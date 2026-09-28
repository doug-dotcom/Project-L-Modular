import hashlib
from pathlib import Path

from services.foundation_companion_service import list_delayed_completion_history


USER = "11111111-1111-4111-8111-111111111111"
VALID_REQUEST = "22222222-2222-4222-8222-222222222222"
BAD_REQUEST = "33333333-3333-4333-8333-333333333333"


class Result:
    def __init__(self, data):
        self.data = data


class Query:
    def __init__(self, rows):
        self.rows = rows
        self.filters = {}
        self.limit_value = None

    def select(self, *_args):
        return self

    def eq(self, key, value):
        self.filters[key] = value
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        rows = [
            dict(row) for row in self.rows
            if all(str(row.get(key)) == str(value) for key, value in self.filters.items())
        ]
        if self.limit_value is not None:
            rows = rows[: self.limit_value]
        return Result(rows)


class FakeDb:
    def __init__(self, rows):
        self.rows = rows

    def table(self, name):
        assert name == "companion_foundation_pending_jobs"
        return Query(self.rows)


def test_delayed_completion_history_returns_only_hash_verified_answers():
    answer = "Your final Vanuatu plan now includes the completed dive brief."
    answer_sha = hashlib.sha256(answer.encode()).hexdigest()
    packet_sha = hashlib.sha256(b"packet").hexdigest()

    db = FakeDb([
        {
            "job_id": VALID_REQUEST,
            "user_id": USER,
            "source_conversation_id": "doug_primary",
            "source_message_id": VALID_REQUEST,
            "request_text": "Plan Vanuatu and include diving",
            "status": "completed",
            "completed_at": "2026-09-28T02:00:00Z",
            "updated_at": "2026-09-28T02:01:00Z",
            "final_result_sha256": packet_sha,
            "final_answer": answer,
            "final_answer_sha256": answer_sha,
            "synthesis_status": "ready",
        },
        {
            "job_id": BAD_REQUEST,
            "user_id": USER,
            "source_conversation_id": "doug_primary",
            "source_message_id": BAD_REQUEST,
            "request_text": "Tampered answer",
            "status": "completed",
            "completed_at": "2026-09-28T02:00:00Z",
            "updated_at": "2026-09-28T02:01:00Z",
            "final_result_sha256": packet_sha,
            "final_answer": "changed after hashing",
            "final_answer_sha256": answer_sha,
            "synthesis_status": "ready",
        },
    ])

    result = list_delayed_completion_history(db, USER, limit=100)

    assert result["status"] == "ok"
    assert result["version"] == "1.0"
    assert result["returned_count"] == 1
    assert result["rejected_count"] == 1
    assert result["items"][0]["request_id"] == VALID_REQUEST
    assert result["items"][0]["final_answer"] == answer
    assert result["items"][0]["integrity"] == "verified"
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
    assert "savedText = delayed.finalAnswer" in index
    assert 'concierge-completions.js?v=190' in index


def test_delayed_final_answer_precedence_does_not_mutate_server_task_history():
    index = Path("ui/index.html").read_text(encoding="utf-8")
    assert "const delayed = run.delayed.get(task.requestId)" in index
    assert "savedText = delayed.finalAnswer" in index
    assert "clearPendingRequest(task.requestId)" in index
    assert "Delayed final answer" in index
