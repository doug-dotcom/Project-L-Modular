import json

from services.concierge_completion_synthesis import (
    synthesise_delayed_concierge_completion,
)


class FixtureAdapter:
    available = True
    provider = "fixture"
    model_id = "fixture-model"

    def __init__(self, content):
        self.content = content
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return {
            "status": "complete",
            "content": self.content,
            "provider": self.provider,
            "model_id": self.model_id,
        }


def planner(_message):
    return {
        "engine": "fixture-controller",
        "version": "1",
        "difficulty": "medium",
        "needs": {
            "memory": True,
            "structured_reasoning": False,
            "longitudinal_reasoning": False,
            "specialist": True,
            "action": False,
        },
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
    assert message == "Plan Vanuatu and include diving"
    assert capability_packet["handled"] is True
    assert capability_packet["reply"]
    assert capability_packet["capability"] == "foundation_orchestration_retry"
    return {
        "engine": "project_l_cognitive_core",
        "version": "13.0",
        "runtime": {"status": "ok"},
        "controller": cognitive_plan,
        "route": {"rike": "not_required"},
        "guardrails": {"passed": True, "issues": []},
        "rike": {"status": "not_required"},
    }


def test_delayed_completion_uses_l_cognition_and_one_final_voice():
    adapter = FixtureAdapter(
        "The delayed dive check is in. Your Vanuatu plan now includes the completed dive brief."
    )
    packet = {
        "status": "completed",
        "reason_code": "concierge-execution-completed",
        "request_id": "request-1",
        "results": [
            {
                "capability_id": "travel.plan_trip",
                "status": "completed",
                "result": {"summary": "Trip complete"},
                "reused": True,
            },
            {
                "capability_id": "dive.destination_brief",
                "status": "completed",
                "result": {"summary": "Dive complete"},
            },
        ],
        "synthesis_ready": True,
        "synthesis_must_disclose_partial": False,
    }

    result = synthesise_delayed_concierge_completion(
        "Plan Vanuatu and include diving",
        packet,
        model_adapter=adapter,
        rhee_builder=lambda _message: {
            "context": "Doug has relevant travel context.",
            "recall_active": True,
            "deep_recall": False,
        },
        cognition_planner=planner,
        cognitive_runner=cognitive_runner,
    )

    assert result["status"] == "ready"
    assert "Vanuatu" in result["reply"]
    request = adapter.requests[0]
    assert request["purpose"] == "l_delayed_concierge_synthesis"
    system = request["messages"][0]["content"]
    assert "You are L." in system
    assert "Never speak as a specialist" in system
    assert "Trip complete" in system


def test_delayed_synthesis_never_runs_without_model():
    class Offline:
        available = False

    result = synthesise_delayed_concierge_completion(
        "Plan Vanuatu and include diving",
        {"status": "completed", "results": []},
        model_adapter=Offline(),
        cognition_planner=planner,
    )
    assert result == {
        "status": "unavailable",
        "reason_code": "delayed-synthesis-model-unavailable",
    }


def test_large_specialist_packet_is_bounded_for_generation():
    adapter = FixtureAdapter("Final answer")
    packet = {
        "status": "completed",
        "reason_code": "done",
        "results": [{
            "capability_id": "travel.plan_trip",
            "status": "completed",
            "result": {"summary": "x" * 30000},
        }],
        "synthesis_ready": True,
    }

    result = synthesise_delayed_concierge_completion(
        "Plan Vanuatu and include diving",
        packet,
        model_adapter=adapter,
        rhee_builder=lambda _message: {
            "context": "",
            "recall_active": False,
            "deep_recall": False,
        },
        cognition_planner=planner,
        cognitive_runner=cognitive_runner,
    )
    assert result["status"] == "ready"
    assert result["result_context_truncated"] is True
    system = adapter.requests[0]["messages"][0]["content"]
    assert len(system) < 30000
