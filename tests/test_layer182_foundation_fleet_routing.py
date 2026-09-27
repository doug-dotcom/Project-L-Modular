from services.capability_router_service import (
    foundation_specialist_interest,
    route_capability,
)


def fleet(*, fiona=True, travel=True):
    specialists = [
        {
            "app_id": "shine.fiona",
            "app_name": "Fiona Finance",
            "capability_id": "fiona.company_brief",
            "display_name": "Company evidence brief",
            "executable": fiona,
            "reason_code": "capability-ready" if fiona else "integration-grant-missing",
            "runtime_available": True,
        },
        {
            "app_id": "shine.travel",
            "app_name": "Shine Travel",
            "capability_id": "travel.plan_trip",
            "display_name": "Plan a trip",
            "executable": travel,
            "reason_code": "capability-ready" if travel else "capability-adapter-quarantined",
            "runtime_available": travel,
        },
    ]
    return {
        "status": "healthy" if fiona and travel else "degraded",
        "specialist_count": 2,
        "executable_count": sum([fiona, travel]),
        "blocked_count": 2 - sum([fiona, travel]),
        "specialists": specialists,
    }


def test_explicit_fiona_intent_uses_live_fleet_state_before_external_research():
    assert foundation_specialist_interest("Fiona: give me a company brief on ASX:ANZ")
    result = route_capability(
        "Fiona: give me a company brief on ASX:ANZ",
        foundation_fleet=fleet(),
    )
    assert result["handled"] is False
    assert result["capability"] == "foundation_specialist"
    assert result["status"] == "ready"
    assert result["foundation_specialist"]["capability_id"] == "fiona.company_brief"
    assert result["foundation_specialist"]["executable"] is True


def test_blocked_specialist_is_not_reported_ready():
    result = route_capability(
        "Shine Travel: plan a trip to Vanuatu",
        foundation_fleet=fleet(travel=False),
    )
    assert result["capability"] == "foundation_specialist"
    assert result["status"] == "blocked"
    assert result["foundation_specialist"]["executable"] is False
    assert result["foundation_specialist"]["reason_code"] == "capability-adapter-quarantined"


def test_ambiguous_specialist_intent_stays_with_l():
    result = route_capability(
        "Plan a trip and give me a dive brief",
        foundation_fleet=fleet(),
    )
    assert result["handled"] is False
    assert result["capability"] == "l_core"
    assert result["status"] == "not_required"


def test_ordinary_conversation_keeps_existing_router_shape():
    assert route_capability("Hello L", foundation_fleet=fleet()) == {
        "handled": False,
        "capability": "l_core",
        "reply": "",
        "status": "not_required",
    }
