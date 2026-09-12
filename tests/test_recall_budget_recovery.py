from datetime import date

from core.cognition.recall_planner import plan_recall, retrieve_period


def test_yesterday_resolves_to_single_day_period():
    plan = plan_recall(
        "Hey L, are you able to recall yesterday's reports please",
        today=date(2026, 9, 12),
    )

    assert plan["mode"] == "period_review"
    assert plan["period"] == {
        "from": "2026-09-11",
        "through": "2026-09-11",
        "timezone": "Australia/Brisbane",
    }
    assert plan["period_source"] == "yesterday"
    assert plan["raw_candidates"] == 24
    assert plan["memory_candidates"] == 12
    assert plan["retrieval_budget_ms"] == 10000
    assert plan["contradiction_review"] is False


class _Response:
    def __init__(self, data):
        self.data = data


class _RpcCall:
    def __init__(self, data):
        self._data = data

    def execute(self):
        return _Response(self._data)


class _Client:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def rpc(self, name, params):
        self.calls.append((name, params))
        return _RpcCall(self.data)


def test_late_bounded_result_is_preserved_instead_of_failing():
    plan = plan_recall(
        "Recall yesterday's reports please",
        today=date(2026, 9, 12),
    )
    client = _Client({
        "months": [
            {
                "month": "2026-09",
                "truncated": False,
                "rows": [
                    {
                        "source": "raw_catchall:123",
                        "content": "Daily report for L — 11 September 2026. Diving and project updates.",
                        "role": "user",
                        "date": "2026-09-11",
                        "date_basis": "event_date",
                        "raw_id": 123,
                        "truncated": False,
                    }
                ],
            }
        ]
    })
    ticks = iter([0.0, 12.0])

    result = retrieve_period(
        client,
        "Recall yesterday's reports please",
        plan,
        ["yesterday", "reports"],
        lambda content: False,
        clock=lambda: next(ticks),
    )

    assert result["receipt"]["status"] == "checked"
    assert result["receipt"]["budget_exceeded"] is True
    assert result["receipt"]["timing_status"] == "late_bounded_result"
    assert result["receipt"]["source_count"] == 1
    assert result["evidence"][0]["source"] == "raw_catchall:123"
    assert "2026-09-11" in result["context"]
    assert client.calls[0][0] == "l_recall_period"
    assert client.calls[0][1]["p_from"] == "2026-09-11"
    assert client.calls[0][1]["p_through"] == "2026-09-11"
