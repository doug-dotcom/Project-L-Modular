import json
from pathlib import Path
from types import SimpleNamespace

from agents.quinn.quinn import curate_principles
from core.cognition.brains_trust import select_lenses
from core.cognition.longitudinal import build_longitudinal_packet
from core.cognition.learning_engine import build_learning_observation, extract_user_learning
from core.cognition.memory_governance import build_memory_payload
from core.cognition.orchestrator import run_cognitive_core
from core.cognition.rike import needs_structured_reasoning, reason
from governance.cognitive_guardrails import assess_cognitive_packet
from services.capability_router_service import route_capability


ROOT = Path(__file__).resolve().parents[1]


class FakeCompletions:
    def create(self, **kwargs):
        self.kwargs = kwargs
        content = json.dumps({
            "activation_reason": "decision_with_competing_evidence",
            "evidence_summary": "Two records support option A and one conflicts.",
            "assumptions": ["The supplied goal is current."],
            "hypotheses": [{"claim": "A", "support": "two records", "counterevidence": "one conflict"}],
            "conflicts": ["One older record supports B."],
            "conclusion": "A is presently better supported.",
            "confidence": {"level": "medium", "score": 0.68, "basis": "Mixed traceable evidence."},
            "uncertainties": ["The goal may have changed."],
            "recommended_action": "Confirm the current goal before acting.",
            "rationale_summary": "A has broader support, but the conflict remains material.",
        })
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class FakeClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=FakeCompletions())


class SequentialCompletions(FakeCompletions):
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("response_format"):
            return super().create(**kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="L's final grounded answer."))]
        )


class SequentialClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=SequentialCompletions())


class MemoryTable:
    def __init__(self, database, name):
        self.database = database
        self.name = name
        self.pending_insert = None

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def insert(self, payload):
        self.pending_insert = payload
        return self

    def execute(self):
        if self.pending_insert is None:
            return SimpleNamespace(data=[])
        self.database.inserts.append((self.name, self.pending_insert))
        return SimpleNamespace(data=[self.pending_insert])


class MemoryDatabase:
    def __init__(self):
        self.inserts = []

    def table(self, name):
        return MemoryTable(self, name)


def test_brains_trust_is_selective_framework_not_persona_swarm():
    names = [item["name"] for item in select_lenses("Compare the risks and system impact")]
    assert "systems" in names
    assert "decision" in names
    assert "uncertainty" in names
    assert len(names) <= 4


def test_rike_activates_for_reasoning_not_ordinary_conversation():
    assert needs_structured_reasoning("How are you?") is False
    assert needs_structured_reasoning("Compare these options and recommend the best one") is True


def test_rike_returns_bounded_inspectable_packet():
    client = FakeClient()
    packet = reason(
        "Compare A and B and recommend the best supported option",
        evidence_context="81 | memory_project_l | source A\n72 | memory_project_l | source B",
        client=client,
    )
    assert packet["status"] == "ok"
    assert packet["confidence"]["level"] == "medium"
    assert packet["rationale_summary"]
    system_prompt = client.chat.completions.kwargs["messages"][0]["content"]
    assert "hidden chain-of-thought" in system_prompt
    assert client.chat.completions.kwargs["temperature"] == 0.15


def test_rike_fails_closed_when_model_is_unavailable():
    packet = reason("Assess the risk", evidence_context="", client=None)
    assert packet["status"] == "degraded"
    assert packet["confidence"]["level"] == "low"
    assert packet["uncertainties"]


def test_mary_requires_multiple_traceable_observations_for_pattern():
    one = build_longitudinal_packet("Is this a pattern again?", "80 | memory_identity | one event")
    assert one["active"] is True
    assert one["pattern_threshold_met"] is False
    assert one["caution"]

    two = build_longitudinal_packet(
        "Has this pattern changed over time?",
        "80 | memory_identity | first\n79 | memory_identity | second",
    )
    assert two["pattern_threshold_met"] is True


def test_quinn_is_a_versioned_advisory_principle_curator():
    packet = curate_principles("Should I decide based on this pattern and risk?")
    ids = {item["id"] for item in packet["principles"]}
    assert "Q-PATTERN-001" in ids
    assert "Q-AGENCY-001" in ids
    assert packet["authority"] == "advisory"
    assert "search_queries" not in packet


def test_guardrails_block_unsupported_pattern_claims():
    packet = {
        "status": "ok",
        "evidence_summary": "one observation",
        "confidence": {"level": "high"},
        "uncertainties": ["none known"],
    }
    assessment = assess_cognitive_packet(
        packet,
        {"active": True, "pattern_threshold_met": False},
    )
    assert assessment["passed"] is False
    assert "pattern_claim_requires_caution" in assessment["issues"]


def test_orchestrator_selectively_connects_rhee_mary_quinn_and_rike():
    simple = run_cognitive_core("Hello L", {"context": "identity context"}, client=FakeClient())
    assert simple["route"]["rike"] == "not_required"

    complex_packet = run_cognitive_core(
        "Compare this pattern over time and recommend what I should do",
        {"context": "80 | memory_identity | first\n79 | memory_identity | second"},
        client=FakeClient(),
    )
    assert complex_packet["route"] == {
        "rhee": "required",
        "mary": "active",
        "quinn": "advisory",
        "rike": "active",
    }
    assert complex_packet["rike"]["status"] == "ok"
    assert complex_packet["guardrails"]["passed"] is True


def test_memory_pipeline_records_only_stages_that_really_ran():
    row = {
        "id": 77,
        "role": "user",
        "content": "I realised Project L needs evidence before confidence again.",
        "created_at": "2026-09-04T01:00:00+00:00",
    }
    promotion = {"promote": True, "reason": "durable_statement", "explicit": False}
    payload, audit = build_memory_payload(row, promotion)
    assert audit["carol"]["target_table"] == "memory_project_l"
    assert payload["processed_by"] == ["carol_v5", "sara_v2", "mary_v4"]
    assert payload["metadata"]["provenance"]["id"] == 77
    assert not ({"coach", "ronnie", "finlay", "chase", "mannie", "gary", "ian", "izzy"} & set(payload["processed_by"]))

    unrelated, unrelated_audit = build_memory_payload(
        {"id": 78, "role": "user", "content": "I learned an analysis technique yesterday."},
        promotion,
    )
    assert unrelated_audit["carol"]["target_table"] == "memory_general"


def test_learning_engine_accepts_explicit_user_learning_not_ai_inference():
    user_row = {
        "id": 12,
        "role": "user",
        "content": "I learned that slowing down before solving the problem prevents overwhelm.",
    }
    candidate = extract_user_learning(user_row)
    assert candidate["lesson"] == "slowing down before solving the problem prevents overwhelm"
    assert candidate["validated"] is True
    assert extract_user_learning({**user_row, "role": "assistant"}) is None
    assert extract_user_learning({**user_row, "content": "L inferred a useful lesson."}) is None


def test_reasoning_output_cannot_promote_itself_to_learning():
    observation = build_learning_observation({"rike": {"status": "ok"}})
    assert observation["status"] == "awaiting_outcome"
    assert observation["auto_promoted"] is False


def test_live_memory_pipeline_executes_governance_and_controlled_learning(monkeypatch):
    from core.cognition import brain_pipeline

    database = MemoryDatabase()
    monkeypatch.setattr(brain_pipeline, "supabase", database)
    result = brain_pipeline.process_raw_memory({
        "id": 91,
        "role": "user",
        "content": "I learned that Project L works best when evidence comes before confidence.",
        "created_at": "2026-09-04T01:00:00+00:00",
    })
    tables = [table for table, _payload in database.inserts]
    memory_payload = next(payload for table, payload in database.inserts if table == "memory_project_l")
    assert result["status"] == "processed"
    assert memory_payload["processed_by"] == ["carol_v5", "sara_v2", "mary_v4"]
    assert "allegra_history" in tables
    assert result["learning"]["reason"] == "candidate_created"


def test_live_server_uses_cognitive_core_and_service_router():
    source = (ROOT / "api" / "server.py").read_text(encoding="utf-8")
    assert "run_cognitive_core" in source
    assert "route_capability" in source
    assert "agents.tegan" not in source
    assert "cognitive_packet" in source
    assert '@app.get("/cognition/status")' in source
    assert '"self_generated_learning_disabled": True' in source
    assert "COGNITIVE TRACE:" in source


def test_project_l_self_audit_contract_names_live_architecture_and_boundaries():
    from api.server import build_architecture_audit_context

    contract = build_architecture_audit_context(
        "L, recall why we created Project L, compare the original architecture and identify contradictions",
        {"route": {"rhee": "required", "rike": "active", "mary": "not_required"}},
    )

    for component in ("L", "Rhee", "RIKE", "Mary", "Quinn", "Carol", "Sara", "Brains Trust"):
        assert component in contract
    assert "historical intent" in contract
    assert "current runtime facts" in contract
    assert "generic feature-rich AI" in contract
    assert '\"rike\": \"active\"' in contract


def test_project_l_self_audit_contract_stays_out_of_ordinary_conversation():
    from api.server import build_architecture_audit_context

    assert build_architecture_audit_context("Good morning L", {}) == (
        "No Project L self-audit requested."
    )


def test_brain_pipeline_no_longer_runs_retired_coach_chain():
    source = (ROOT / "core" / "cognition" / "brain_pipeline.py").read_text(encoding="utf-8")
    assert "build_memory_payload" in source
    assert "run_memory_to_coach" not in source
    assert "COACH STORED" not in source


def test_external_research_runtime_no_longer_calls_rat_pack_personas():
    router = (ROOT / "services" / "capability_router_service.py").read_text(encoding="utf-8")
    research = (ROOT / "services" / "external_research_service.py").read_text(encoding="utf-8")
    combined = router + research
    assert "agents.brittany" not in combined
    assert "run_rat_pack" not in combined
    assert "agents.polly" not in combined


def test_ordinary_conversation_does_not_load_or_activate_connector_personas():
    assert route_capability("Hello L") == {
        "handled": False,
        "capability": "l_core",
        "reply": "",
        "status": "not_required",
    }
    source = (ROOT / "services" / "google_workspace_service.py").read_text(encoding="utf-8")
    assert "agents.emily" not in source
    assert "agents.callie" not in source
    assert "agents.tanya" not in source


def test_capability_results_are_reasoning_evidence_but_l_remains_final_voice():
    client = FakeClient()
    packet = run_cognitive_core(
        "Compare the current sources and recommend the best option",
        {"context": "Rhee evidence"},
        capability_packet={
            "handled": True,
            "capability": "external_research",
            "status": "ok",
            "reply": "Source A supports the current result.",
        },
        client=client,
    )
    model_payload = json.loads(client.chat.completions.kwargs["messages"][1]["content"])
    assert "GOVERNED CAPABILITY RESULT" in model_payload["evidence_context"]
    assert "Source A supports" in model_payload["evidence_context"]
    server = (ROOT / "api" / "server.py").read_text(encoding="utf-8")
    assert "A capability result is evidence or an action receipt" in server


def test_chat_runs_rike_then_returns_only_ls_final_voice(monkeypatch):
    from api import server

    client = SequentialClient()
    monkeypatch.setattr(server, "client", client)
    monkeypatch.setattr(
        server,
        "build_rhee_packet",
        lambda _message: {
            "context": "LONG TERM RECALL ACTIVE: True\n80 | memory_project_l | verified record",
            "recall_active": True,
            "short_term_domain": "project_l",
        },
    )
    monkeypatch.setattr(
        server,
        "route_capability",
        lambda _message: {"handled": False, "capability": "l_core", "reply": "", "status": "not_required"},
    )
    monkeypatch.setattr(server, "write_raw_catchall", lambda role, content, source="chat": {"id": 1, "role": role, "content": content})
    monkeypatch.setattr(server, "run_brain_pipeline", lambda _row: None)
    monkeypatch.setattr(server, "write_live_short_term", lambda *_args: {"saved": True})
    monkeypatch.setattr(server, "voice_enabled", lambda: False)

    result = server.chat(server.ChatRequest(message="Compare the evidence and recommend what we should do"))

    assert result["reply"] == "L's final grounded answer."
    assert result["cognition"]["rike_status"] == "ok"
    assert result["cognition"]["route"]["rike"] == "active"
    assert len(client.chat.completions.calls) == 2
    assert client.chat.completions.calls[0].get("response_format") == {"type": "json_object"}
    assert client.chat.completions.calls[1].get("response_format") is None
