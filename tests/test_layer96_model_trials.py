import json
from types import SimpleNamespace as NS

import pytest

from core.cognition.model_trials import grade_trial, run_model_trials, trial_cases, trial_manifest


class Adapter:
    available = True
    provider = "fixture"

    def __init__(self, name="fixture-a", *, fail=False, alias=False):
        self.model_id, self.fail, self.alias = name, fail, alias
        self.calls = []

    def generate(self, request):
        self.calls.append(request)
        if self.fail:
            raise RuntimeError("private provider credential text")
        return {"content": '{"reply":"A fixture response."}',
                "model_id": self.model_id+"-snapshot" if self.alias else self.model_id,
                "receipt": {"usage": {"input_tokens": 10}, "cost": {"status": "not_priced"}}}


def case(name):
    return next(c for c in trial_cases() if c["id"] == name)


def test_plan_is_stable_and_has_three_separate_suites():
    plan = trial_manifest(["model-a", "model-b"], 2)
    assert plan["planned_calls"] == 36
    assert plan["case_set_sha256"] == trial_manifest(["model-b"], 1)["case_set_sha256"]
    assert {c["suite"] for c in plan["cases"]} == {"conversation", "recall", "reasoning"}
    assert plan["route_changes"] is False


@pytest.mark.parametrize("models,repeats", [([], 1), (["a", "a"], 1), (["a"]*4, 1), (["a"], 0), (["a"], True)])
def test_invalid_or_unbounded_plans_are_rejected(models, repeats):
    with pytest.raises(ValueError):
        trial_manifest(models, repeats)


@pytest.mark.parametrize("name,answer", [
    ("recall_source", {"source": "memory_preferences:7"}),
    ("recall_correction", {"current_day": "Tuesday", "superseded_day": "Monday"}),
    ("recall_absence", {"status": "unknown", "serial_number": None}),
    ("reasoning_dependencies", {"order": ["A", "C", "B", "D"]}),
    ("reasoning_causality", {"cause_established": False}),
    ("reasoning_constraints", {"departure": "09:00"}),
])
def test_objective_fixture_checks(name, answer):
    assert grade_trial(case(name), json.dumps(answer))["status"] == "fixture_checks_passed"


def test_missing_null_false_numeric_coercion_and_wrong_order_fail():
    assert grade_trial(case("recall_absence"), '{"status":"unknown"}')["status"] == "failed"
    assert grade_trial(case("reasoning_causality"), '{"cause_established":0}')["status"] == "failed"
    assert grade_trial(case("reasoning_dependencies"), '{"order":["D","A","B","C"]}')["status"] == "failed"


@pytest.mark.parametrize("content", ["not JSON", "[]", "null", '{"reply":""}'])
def test_unusable_conversation_output_fails(content):
    assert grade_trial(case("conversation_overload"), content)["status"] == "failed"


def test_fluent_conversation_is_not_automatically_good_behaviour():
    grade = grade_trial(case("conversation_boundary"), '{"reply":"I booked it for you."}')
    assert grade["status"] == "review_required"
    assert "Do not claim an action was completed" in grade["rubric"]


def test_separate_results_retain_prompts_receipts_and_review_pending():
    a, b = Adapter(), Adapter("fixture-b")
    result = run_model_trials([a, b], repeats=1)
    assert len(a.calls) == len(b.calls) == 9
    assert len(result["summaries"]) == 6
    assert len(result["results"]) == 18
    assert result["promotion_eligible"] is False
    assert all(x["request_sha256"] == y["request_sha256"] for x, y in zip(a.calls, b.calls))
    assert {r["status"] for r in result["results"] if r["suite"] == "conversation"} == {"review_required"}
    assert result["results"][0]["receipt"]["usage"]["input_tokens"] == 10
    assert all(s["recorded_cost"]["priced_calls"] == 0 for s in result["summaries"])
    assert all(s["recorded_cost"]["unpriced_attempts"] == 3 for s in result["summaries"])


def test_error_stops_only_failed_candidate_and_does_not_leak_exception():
    a, b = Adapter(fail=True), Adapter("fixture-b")
    result = run_model_trials([a, b], repeats=2)
    assert len(a.calls) == 1 and len(b.calls) == 18
    rows = [r for r in result["results"] if r["model"] == a.model_id]
    assert len(rows) == 18
    assert sum(r["status"] == "not_run" for r in rows) == 17
    assert "private provider" not in json.dumps(result)


def test_deadline_keeps_unexecuted_cases_visible():
    a = Adapter()
    moments = iter([0, 301]+[301]*20)
    result = run_model_trials([a], repeats=1, clock=lambda: next(moments))
    assert a.calls == []
    assert len(result["results"]) == 9
    assert all(r["status"] == "not_run" for r in result["results"])


def test_unavailable_model_blocks_before_any_calls():
    a = Adapter()
    b = Adapter("fixture-b")
    b.available = False
    with pytest.raises(RuntimeError, match="unavailable"):
        run_model_trials([a, b])
    assert a.calls == []


def test_alias_review_does_not_hide_a_failed_answer():
    result = run_model_trials([Adapter(alias=True)], repeats=1)
    assert all(r["status"] == "failed" for r in result["results"] if r["suite"] != "conversation")
    assert all("model_identity_review" in r for r in result["results"])


def test_command_plans_without_credentials_or_calls(monkeypatch, capsys):
    from scripts import run_model_trials as command
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(command, "OpenAI", lambda **kw: pytest.fail("Plan opened provider client"))
    monkeypatch.setattr("sys.argv", ["run_model_trials", "--models", "model-a"])
    assert command.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "planned_not_executed"


def test_command_execution_requires_credentials(monkeypatch, capsys):
    from scripts import run_model_trials as command
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(command, "load_dotenv", lambda: None)
    monkeypatch.setattr(command, "OpenAI", lambda **kw: pytest.fail("Missing credential opened client"))
    monkeypatch.setattr("sys.argv", ["run_model_trials", "--models", "model-a", "--run"])
    with pytest.raises(SystemExit) as exc:
        command.main()
    assert exc.value.code == 2
    assert "no model calls" in capsys.readouterr().err
