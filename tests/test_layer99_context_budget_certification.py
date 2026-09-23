"""Layer 99 regression tests for context-budget quality certification."""

import json
from types import SimpleNamespace as NS

import pytest

from core.cognition.context_budget_trials import (
    build_trial_prompt,
    grade_trial,
    run_context_budget_trials,
    trial_cases,
    trial_manifest,
)


class Adapter:
    available = True
    provider = "fixture"

    def __init__(self, name="fixture-a", *, fail=False):
        self.model_id = name
        self.fail = fail
        self.calls = []

    def generate(self, request):
        self.calls.append(request)
        if self.fail:
            raise RuntimeError("private provider error text")
        user = request["messages"][-1]["content"]
        if "storage locker" in user:
            content = '{"code":"2719","source":"raw_catchall:4"}'
        elif "workshop starts" in user:
            content = '{"departure":"09:00"}'
        elif "slept longer" in user:
            content = '{"cause_established":false}'
        else:
            content = '{"reply":"That sounds like a lot. Pick the smallest task and do only its first step."}'
        return {
            "content": content,
            "model_id": self.model_id,
            "receipt": {
                "usage": {"input_tokens": 10},
                "cost": {"status": "not_priced"},
            },
        }


def case(name):
    return next(item for item in trial_cases() if item["id"] == name)


def test_manifest_is_bounded_synthetic_and_non_mutating():
    plan = trial_manifest(["model-a"], 1)
    assert plan["planned_calls"] == 8
    assert plan["variants"] == ["full", "budgeted"]
    assert plan["private_memory_reads"] is False
    assert plan["memory_writes"] is False
    assert plan["route_changes"] is False
    assert plan["automatic_promotion"] is False

    largest = trial_manifest(["model-a", "model-b"], 2)
    assert largest["planned_calls"] == 32


@pytest.mark.parametrize(
    "models,repeats",
    [
        ([], 1),
        (["a", "a"], 1),
        (["a", "b", "c"], 1),
        (["a"], 0),
        (["a"], 3),
        (["a"], True),
    ],
)
def test_unbounded_or_invalid_plans_are_rejected(models, repeats):
    with pytest.raises(ValueError):
        trial_manifest(models, repeats)


def test_budgeted_lean_prompt_is_smaller_but_keeps_same_user_request():
    item = case("conversation_small_start")
    full = build_trial_prompt(item, "full")
    budgeted = build_trial_prompt(item, "budgeted")

    assert full["messages"][-1] == budgeted["messages"][-1]
    assert budgeted["context_receipt"]["mode"] == "lean"
    assert budgeted["context_receipt"]["rendered_chars"] < full["context_receipt"]["rendered_chars"]
    assert "inactive diagnostic detail" in full["messages"][0]["content"]
    assert "inactive diagnostic detail" not in budgeted["messages"][0]["content"]


def test_budgeting_never_changes_synthetic_rhee_evidence():
    item = case("recall_exact_source")
    full = build_trial_prompt(item, "full")
    budgeted = build_trial_prompt(item, "budgeted")

    evidence = item["evidence"]
    assert evidence in full["messages"][0]["content"]
    assert evidence in budgeted["messages"][0]["content"]
    assert budgeted["context_receipt"]["rhee_evidence_modified"] is False
    assert budgeted["context_receipt"]["mode"] == "expanded"


@pytest.mark.parametrize(
    "name,answer",
    [
        ("recall_exact_source", {"code": "2719", "source": "raw_catchall:4"}),
        ("reasoning_latest_departure", {"departure": "09:00"}),
        ("reasoning_causal_boundary", {"cause_established": False}),
    ],
)
def test_objective_fixture_checks(name, answer):
    assert grade_trial(case(name), json.dumps(answer))["status"] == "fixture_checks_passed"


def test_conversation_is_never_automatically_certified():
    result = grade_trial(
        case("conversation_small_start"),
        '{"reply":"Pick one tiny first action."}',
    )
    assert result["status"] == "review_required"
    assert result["rubric"]


def test_full_vs_budgeted_runner_reports_objective_parity_and_human_review():
    adapter = Adapter()
    result = run_context_budget_trials([adapter], repeats=1)

    assert len(adapter.calls) == 8
    assert len(result["results"]) == 8
    assert len(result["pairs"]) == 4
    assert result["objective_parity"] == "passed"
    assert result["conversation_review_pending"] is True
    assert result["certification_status"] == "review_required"
    assert result["promotion_eligible"] is False
    assert result["route_changes"] is False

    objective = [pair for pair in result["pairs"] if pair["suite"] != "conversation"]
    assert objective
    assert all(pair["status"] == "objective_parity" for pair in objective)
    conversation = [pair for pair in result["pairs"] if pair["suite"] == "conversation"]
    assert conversation[0]["status"] == "review_required"

    budgeted = [row for row in result["results"] if row["variant"] == "budgeted"]
    assert all(row["context_receipt"]["rhee_evidence_modified"] is False for row in budgeted)
    assert result["summaries"][0]["budget_reduction_ratio"]["observed"] == 4


def test_provider_failure_stops_candidate_without_leaking_exception_text():
    result = run_context_budget_trials([Adapter(fail=True)], repeats=1)
    assert result["results"][0]["status"] == "error"
    assert all(row["status"] == "not_run" for row in result["results"][1:])
    assert "private provider error" not in json.dumps(result)


def test_command_plans_without_credentials_or_provider_calls(monkeypatch, capsys):
    from scripts import run_context_budget_trials as command

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(command, "OpenAI", lambda **kw: pytest.fail("Plan opened provider"))
    monkeypatch.setattr(
        "sys.argv",
        ["run_context_budget_trials", "--models", "model-a"],
    )
    assert command.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "planned_not_executed"
    assert output["planned_calls"] == 8


def test_command_execution_requires_credentials(monkeypatch, capsys):
    from scripts import run_context_budget_trials as command

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(command, "load_dotenv", lambda: None)
    monkeypatch.setattr(command, "OpenAI", lambda **kw: pytest.fail("Missing key opened provider"))
    monkeypatch.setattr(
        "sys.argv",
        ["run_context_budget_trials", "--models", "model-a", "--run"],
    )
    with pytest.raises(SystemExit) as exc:
        command.main()
    assert exc.value.code == 2
    assert "no model calls" in capsys.readouterr().err


def test_real_chat_handler_sends_budgeted_not_full_inactive_cognition(monkeypatch):
    from api import server
    from core.cognition.model_independence import OpenAIChatCompletionsAdapter

    marker = "LAYER99-INACTIVE-MARKER-MUST-NOT-REACH-MODEL"
    captured = []
    reply = "One small first step is enough."

    client = NS(
        chat=NS(
            completions=NS(
                create=lambda **kw: NS(
                    id="layer99-fixture",
                    model="test",
                    choices=[NS(finish_reason="stop", message=NS(content=reply))],
                )
            )
        )
    )

    class CapturingAdapter(OpenAIChatCompletionsAdapter):
        def generate(self, request):
            captured.append(request)
            return super().generate(request)

    monkeypatch.setattr(
        server,
        "resolve_model_adapter",
        lambda: CapturingAdapter(client, model_id="test"),
    )
    monkeypatch.setattr(
        server,
        "route_capability",
        lambda _: {"handled": False, "status": "not_required"},
    )

    def cognitive(*args, **kwargs):
        plan = kwargs["cognitive_plan"]
        return {
            "engine": "project_l_cognitive_core",
            "version": "13.0",
            "runtime": {"status": "complete", "fallback_used": False},
            "controller": plan,
            "route": {
                "rike": "not_required",
                "mary": "not_required",
                "confidence_evidence": "active",
            },
            "guardrails": {"passed": True, "issues": []},
            "confidence_dimensions": {"status": "complete"},
            "confidence_evidence": {"status": "complete"},
            "rike": {"status": "not_required", "detail": marker},
            "mary": {"active": False, "detail": marker},
            "working_memory": kwargs.get("working_memory_packet") or {},
            "model_independence": {"foundation_model_is_replaceable": True},
            "portability": {"status": "available"},
        }

    monkeypatch.setattr(server, "run_cognitive_core", cognitive)
    monkeypatch.setattr(
        server,
        "write_raw_catchall",
        lambda role, content, **kw: {"id": 99, "role": role, "content": content},
    )
    monkeypatch.setattr(
        server,
        "write_live_short_term",
        lambda *a, **kw: {"saved": False},
    )
    monkeypatch.setattr(server, "run_brain_pipeline", lambda *a, **kw: None)
    monkeypatch.setattr(server, "voice_enabled", lambda: False)

    result = server.chat(server.ChatRequest(message="Hello L"))

    assert result["reply"] == reply
    assert captured
    system_prompt = captured[0]["messages"][0]["content"]
    assert "COGNITIVE CONTEXT BUDGET:" in system_prompt
    assert marker not in system_prompt
    assert result["cognition"]["context_budget"]["mode"] == "lean"
    assert result["cognition"]["context_budget"]["stored_cognitive_packet_modified"] is False
