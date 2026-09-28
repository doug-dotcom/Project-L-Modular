import json

from services.concierge_planner_service import plan_concierge_specialists
from services.capability_router_service import needs_concierge_planning, route_capability


class FixtureAdapter:
    available = True
    provider = "fixture"
    model_id = "fixture-model"

    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return {
            "status": "complete",
            "content": json.dumps(self.payload),
            "provider": self.provider,
            "model_id": self.model_id,
        }


def fleet(*, travel=True, dive=True, fiona=True):
    return {
        "status": "healthy",
        "specialists": [
            {
                "capability_id": "travel.plan_trip",
                "app_name": "Shine Travel",
                "display_name": "Plan a trip",
                "executable": travel,
                "reason_code": "capability-ready" if travel else "integration-grant-missing",
                "runtime_available": travel,
            },
            {
                "capability_id": "dive.destination_brief",
                "app_name": "Shine Dive",
                "display_name": "Destination dive brief",
                "executable": dive,
                "reason_code": "capability-ready" if dive else "capability-adapter-quarantined",
                "runtime_available": dive,
            },
            {
                "capability_id": "fiona.company_brief",
                "app_name": "Fiona Finance",
                "display_name": "Company evidence brief",
                "executable": fiona,
                "reason_code": "capability-ready" if fiona else "integration-grant-missing",
                "runtime_available": fiona,
            },
        ],
    }


def test_shine_ai_can_select_multiple_live_specialists_but_not_construct_inputs():
    adapter = FixtureAdapter({
        "selectedCapabilities": ["travel.plan_trip", "dive.destination_brief"],
        "clarificationNeeded": False,
        "clarifyingQuestion": "",
    })
    plan = plan_concierge_specialists(
        "Plan a trip to Vanuatu and give me a dive brief for Vanuatu",
        fleet(),
        model_adapter=adapter,
        l_context="Doug enjoys diving.",
    )
    assert plan["status"] == "ready"
    assert plan["selected_capabilities"] == [
        "travel.plan_trip",
        "dive.destination_brief",
    ]
    assert [step["input_contract"]["input_data"] for step in plan["steps"]] == [
        {"destination": "Vanuatu"},
        {"destination": "Vanuatu"},
    ]
    assert plan["governance"]["selection_only"] is True
    assert plan["governance"]["inputs_compiled_deterministically"] is True
    assert plan["governance"]["execution_performed"] is False

    request = adapter.requests[0]
    assert request["purpose"] == "shine_concierge_capability_planning"
    assert request["response_format"]["type"] == "json_schema"
    prompt = request["messages"][0]["content"]
    assert "do not create specialist arguments" in prompt.lower()


def test_blocked_specialist_stays_blocked_even_when_model_selects_it():
    adapter = FixtureAdapter({
        "selectedCapabilities": ["dive.destination_brief"],
        "clarificationNeeded": False,
        "clarifyingQuestion": "",
    })
    plan = plan_concierge_specialists(
        "Give me a dive brief for Vanuatu",
        fleet(dive=False),
        model_adapter=adapter,
    )
    assert plan["status"] == "blocked"
    assert plan["steps"][0]["status"] == "blocked"
    assert plan["steps"][0]["reason_code"] == "capability-adapter-quarantined"


def test_missing_required_input_is_not_filled_from_l_context():
    adapter = FixtureAdapter({
        "selectedCapabilities": ["travel.plan_trip"],
        "clarificationNeeded": True,
        "clarifyingQuestion": "Where would you like to go?",
    })
    plan = plan_concierge_specialists(
        "Plan me a trip",
        fleet(),
        model_adapter=adapter,
        l_context="Previous conversations mentioned Vanuatu.",
    )
    assert plan["status"] == "needs_input"
    assert plan["steps"][0]["input_contract"]["missing_fields"] == ["destination"]
    assert "input_data" not in plan["steps"][0]["input_contract"]
    assert plan["clarifying_question"] == "Where would you like to go?"


def test_unknown_or_duplicate_model_capabilities_fail_closed():
    unknown = FixtureAdapter({
        "selectedCapabilities": ["travel.plan_trip", "made.up"],
        "clarificationNeeded": False,
        "clarifyingQuestion": "",
    })
    assert plan_concierge_specialists(
        "Plan a trip to Vanuatu",
        fleet(),
        model_adapter=unknown,
    )["reason_code"] == "shine-ai-plan-invalid"

    duplicate = FixtureAdapter({
        "selectedCapabilities": ["travel.plan_trip", "travel.plan_trip"],
        "clarificationNeeded": False,
        "clarifyingQuestion": "",
    })
    assert plan_concierge_specialists(
        "Plan a trip to Vanuatu",
        fleet(),
        model_adapter=duplicate,
    )["reason_code"] == "shine-ai-plan-invalid"


def test_no_specialist_selection_is_not_required():
    adapter = FixtureAdapter({
        "selectedCapabilities": [],
        "clarificationNeeded": False,
        "clarifyingQuestion": "",
    })
    plan = plan_concierge_specialists(
        "Tell me a joke",
        fleet(),
        model_adapter=adapter,
    )
    assert plan["status"] == "not_required"
    assert plan["steps"] == []


def test_ambiguous_multi_domain_request_requires_shine_ai_planning():
    assert needs_concierge_planning(
        "Plan a trip to Vanuatu and give me a dive brief for Vanuatu"
    ) is True
    assert needs_concierge_planning(
        "Fiona: give me a company brief on ASX:ANZ"
    ) is False


def test_valid_multi_specialist_plan_becomes_one_governed_orchestration_route():
    adapter = FixtureAdapter({
        "selectedCapabilities": ["travel.plan_trip", "dive.destination_brief"],
        "clarificationNeeded": False,
        "clarifyingQuestion": "",
    })
    plan = plan_concierge_specialists(
        "Plan a trip to Vanuatu and give me a dive brief for Vanuatu",
        fleet(),
        model_adapter=adapter,
    )
    route = route_capability(
        "Plan a trip to Vanuatu and give me a dive brief for Vanuatu",
        foundation_fleet=fleet(),
        concierge_plan=plan,
    )
    assert route["handled"] is False
    assert route["capability"] == "foundation_orchestration"
    assert route["status"] == "ready"
    assert route["foundation_orchestration"]["selected_capabilities"] == [
        "travel.plan_trip",
        "dive.destination_brief",
    ]


def test_server_wires_rhee_context_and_active_model_into_concierge_planner():
    from pathlib import Path

    source = Path("api/server.py").read_text(encoding="utf-8")
    call = "plan_concierge_specialists("
    index = source.index(call, source.index("def chat("))
    window = source[index:index + 500]
    assert "user_message" in window
    assert "foundation_fleet" in window
    assert "model_adapter=active_model_adapter" in window
    assert "l_context=rhee_context" in window
    assert "concierge_plan=concierge_plan" in source



def test_multi_domain_shine_request_never_falls_through_when_planner_is_unavailable():
    route = route_capability(
        "Plan a trip to Vanuatu and give me a dive brief for Vanuatu",
        foundation_fleet=None,
        concierge_plan=None,
    )
    assert route["capability"] == "foundation_orchestration"
    assert route["status"] == "unavailable"
    assert (
        route["foundation_orchestration"]["reason_code"]
        == "concierge-planning-unavailable"
    )
