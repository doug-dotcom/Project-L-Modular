from services.concierge_specialist_inputs import compile_specialist_input
from services.capability_router_service import route_capability


def test_all_live_foundation_specialists_compile_to_their_declared_shapes():
    cases = {
        "fiona.company_brief": (
            "Fiona: give me a company brief on ASX:ANZ, focusing on risks",
            {"identifier": "ASX:ANZ", "focus": "risks"},
        ),
        "money.explain_calculate": (
            "Shine My Money: explain compound interest on $10,000",
            {"question": "Shine My Money: explain compound interest on $10,000"},
        ),
        "travel.plan_trip": (
            "Shine Travel: plan a trip to Vanuatu",
            {"destination": "Vanuatu"},
        ),
        "dive.destination_brief": (
            "Shine Dive: give me a dive brief for Tulamben with Advanced Open Water and Nitrox",
            {
                "destination": "Tulamben",
                "certifications": ["Advanced Open Water", "Enriched Air Nitrox"],
            },
        ),
        "fish.destination_brief": (
            "Shine Fish: fishing brief for Moreton Bay targeting snapper",
            {
                "destination": "Moreton Bay",
                "species": "snapper",
                "query": "Shine Fish: fishing brief for Moreton Bay targeting snapper",
            },
        ),
        "ski.destination_brief": (
            "Shine Ski: snow brief for Niseko with intermediate ability",
            {"destination": "Niseko", "ability": "intermediate"},
        ),
        "daash.exercise_explain": (
            "DaAsh: explain exercise Romanian deadlift",
            {
                "exercise": "Romanian deadlift",
                "question": "DaAsh: explain exercise Romanian deadlift",
            },
        ),
        "translate.text": (
            'Shine Translate: translate "Good morning" from English to Japanese',
            {
                "text": "Good morning",
                "sourceLanguage": "en",
                "targetLanguage": "ja",
            },
        ),
        "dnd.campaign_context": (
            "Shine D&D: what do we know about the current campaign?",
            {"query": "Shine D&D: what do we know about the current campaign?"},
        ),
    }

    for capability_id, (message, expected) in cases.items():
        result = compile_specialist_input(capability_id, message)
        assert result["status"] == "ready", (capability_id, result)
        assert result["reason_code"] == "specialist-input-ready"
        assert result["input_data"] == expected
        assert result["missing_fields"] == []
        assert result["compiler"] == "deterministic-foundation-contract-v1"


def test_missing_required_fields_are_reported_not_guessed():
    travel = compile_specialist_input("travel.plan_trip", "Shine Travel: plan a trip")
    assert travel["status"] == "needs_input"
    assert travel["missing_fields"] == ["destination"]
    assert "input_data" not in travel

    translation = compile_specialist_input(
        "translate.text",
        'Shine Translate: translate "Hello" to Japanese',
    )
    assert translation["status"] == "needs_input"
    assert translation["missing_fields"] == ["sourceLanguage"]
    assert "input_data" not in translation


def test_unknown_capability_never_gets_an_ad_hoc_payload():
    result = compile_specialist_input("unknown.make_something_up", "Do anything")
    assert result == {
        "status": "unsupported",
        "reason_code": "specialist-input-contract-unsupported",
        "capability_id": "unknown.make_something_up",
        "compiler": "deterministic-foundation-contract-v1",
        "missing_fields": [],
    }


def test_router_marks_executable_specialist_needs_input_until_contract_is_complete():
    fleet = {
        "status": "healthy",
        "specialist_count": 1,
        "executable_count": 1,
        "blocked_count": 0,
        "specialists": [{
            "app_id": "shine.travel",
            "app_name": "Shine Travel",
            "capability_id": "travel.plan_trip",
            "display_name": "Plan a trip",
            "executable": True,
            "reason_code": "capability-ready",
            "runtime_available": True,
        }],
    }
    route = route_capability("Shine Travel: plan a trip", foundation_fleet=fleet)
    assert route["status"] == "needs_input"
    packet = route["foundation_specialist"]
    assert packet["executable"] is True
    assert packet["input_contract"]["status"] == "needs_input"
    assert packet["input_contract"]["missing_fields"] == ["destination"]


def test_router_carries_only_compiled_foundation_input_when_ready():
    fleet = {
        "status": "healthy",
        "specialist_count": 1,
        "executable_count": 1,
        "blocked_count": 0,
        "specialists": [{
            "app_id": "shine.fiona",
            "app_name": "Fiona Finance",
            "capability_id": "fiona.company_brief",
            "display_name": "Company evidence brief",
            "executable": True,
            "reason_code": "capability-ready",
            "runtime_available": True,
        }],
    }
    route = route_capability(
        "Fiona: give me a company brief on ASX:ANZ",
        foundation_fleet=fleet,
    )
    assert route["status"] == "ready"
    assert route["foundation_specialist"]["input_contract"]["input_data"] == {
        "identifier": "ASX:ANZ"
    }
