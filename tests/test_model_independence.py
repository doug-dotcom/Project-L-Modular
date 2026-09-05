import json

import pytest

from core.cognition.model_independence import (
    PERSISTENT_SYSTEMS,
    OpenAIChatCompletionsAdapter,
    build_model_independence_packet,
    build_model_request,
    invoke_model,
)
from core.cognition.orchestrator import run_cognitive_core
from core.cognition.rike import reason


class FixtureAdapter:
    available = True

    def __init__(self, provider="fixture", model_id="fixture-model", content="fixture output"):
        self.provider = provider
        self.model_id = model_id
        self.content = content
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return {"status": "complete", "content": self.content}


def test_phase_eleven_standard_request_and_result_contract_survives_provider_swap():
    request = build_model_request(
        [{"role": "user", "content": "Hello L"}],
        purpose="provider_swap_test",
        temperature=0.4,
        max_output_tokens=500,
    )
    first = invoke_model(FixtureAdapter("provider-a", "model-a"), request)
    second = invoke_model(FixtureAdapter("provider-b", "model-b"), request)
    assert set(first) == set(second)
    assert first["content"] == second["content"] == "fixture output"
    assert first["provider"] == "provider-a"
    assert second["provider"] == "provider-b"
    assert first["interface_version"] == second["interface_version"] == "1.0"


def test_phase_eleven_rejects_malformed_provider_neutral_requests():
    with pytest.raises(ValueError, match="model_messages_required"):
        build_model_request([], purpose="invalid")
    with pytest.raises(ValueError, match="model_message_role_invalid"):
        build_model_request([{"role": "owner", "content": "bad role"}], purpose="invalid")
    adapter = FixtureAdapter()
    with pytest.raises(ValueError, match="model_interface_version_mismatch"):
        invoke_model(adapter, {"interface_version": "99.0"})


def test_phase_eleven_manifest_keeps_all_canonical_systems_outside_model_ownership():
    packet = build_model_independence_packet(FixtureAdapter("provider-a", "model-a"))
    persistent = set(packet["contract"]["persistent_systems"])
    assert set(PERSISTENT_SYSTEMS) == persistent
    assert {
        "metacognition", "rike_reasoning", "rhee_retrieval",
        "mary_longitudinal_intelligence", "quinn_governed_principles",
        "sara_memory_governance", "carol_evidence_hygiene",
        "specialist_services", "supabase_memory_and_cognitive_history",
    } == persistent
    assert packet["governance"]["foundation_model_is_replaceable"] is True
    assert packet["governance"]["foundation_model_owns_identity"] is False
    assert packet["governance"]["foundation_model_owns_memory"] is False
    assert packet["governance"]["foundation_model_owns_evidence"] is False
    assert packet["governance"]["foundation_model_can_bypass_governance"] is False
    assert packet["governance"]["persistent_systems_survive_model_swap"] is True


def test_phase_eleven_openai_translation_is_isolated_inside_adapter():
    class Message:
        content = "translated output"

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]

    class Completions:
        def __init__(self):
            self.options = None

        def create(self, **options):
            self.options = options
            return Response()

    class Chat:
        def __init__(self):
            self.completions = Completions()

    class Client:
        def __init__(self):
            self.chat = Chat()

    client = Client()
    adapter = OpenAIChatCompletionsAdapter(client, "replaceable-model")
    request = build_model_request(
        [{"role": "user", "content": "test"}],
        purpose="translation_test",
        response_format={"type": "json_object"},
    )
    result = invoke_model(adapter, request)
    assert result["content"] == "translated output"
    assert result["provider"] == "openai"
    assert client.chat.completions.options["model"] == "replaceable-model"
    assert client.chat.completions.options["response_format"] == {"type": "json_object"}


def test_phase_eleven_rike_uses_standard_adapter_without_provider_client():
    payload = {
        "activation_reason": "fixture",
        "evidence_summary": "fixture evidence",
        "assumptions": [],
        "hypotheses": [
            {"claim": "A", "status": "plausible"},
            {"claim": "B", "status": "insufficient"},
        ],
        "conflicts": [],
        "alternative_explanations": ["B"],
        "conclusion_change_evidence": ["new evidence"],
        "counterfactuals": [],
        "conclusion": "A is more plausible.",
        "confidence": {"level": "medium", "score": 0.6, "basis": "fixture"},
        "uncertainties": ["fixture uncertainty"],
        "recommended_action": "Review.",
        "rationale_summary": "Bounded fixture rationale.",
        "direct_causal_evidence": {"established": False, "evidence_quotes": []},
        "causal_assessment": {"relationship": "none", "supported_causal_claim": False},
    }
    adapter = FixtureAdapter(content=json.dumps(payload))
    packet = reason("Compare A and B", model_adapter=adapter)
    assert packet["status"] == "ok"
    assert adapter.requests[0]["purpose"] == "rike_structured_reasoning"


def test_phase_eleven_cognitive_core_exposes_active_model_contract():
    adapter = FixtureAdapter("provider-a", "model-a")
    packet = run_cognitive_core(
        "Hello L",
        {"context": "", "recall_active": False},
        capability_packet={},
        model_adapter=adapter,
    )
    assert packet["version"] == "13.0"
    assert packet["model_independence"]["status"] == "ready"
    assert packet["model_independence"]["active_adapter"]["provider"] == "provider-a"


def test_phase_eleven_live_model_calls_are_centralised_in_one_adapter():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    server = (root / "api" / "server.py").read_text(encoding="utf-8")
    rike = (root / "core" / "cognition" / "rike.py").read_text(encoding="utf-8")
    adapter = (root / "core" / "cognition" / "model_independence.py").read_text(encoding="utf-8")
    assert "client.chat.completions.create" not in server
    assert "client.chat.completions.create" not in rike
    assert adapter.count("client.chat.completions.create") == 1
    assert '"version": "13.0"' in server
    assert '"model_independence": "model_independence_layer_v1"' in server
    assert '"foundation_model_is_replaceable": True' in server
    assert '"model_independence": cognitive_packet.get("model_independence", {})' in server
