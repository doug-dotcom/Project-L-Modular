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
from core.cognition.controller import finalise_cognition_plan, plan_cognition
from core.cognition.uncertainty import DIMENSIONS, assess_confidence_dimensions


ROOT = Path(__file__).resolve().parents[1]


class FakeCompletions:
    def create(self, **kwargs):
        self.kwargs = kwargs
        content = json.dumps({
            "activation_reason": "decision_with_competing_evidence",
            "evidence_summary": "Two records support option A and one conflicts.",
            "assumptions": ["The supplied goal is current."],
            "hypotheses": [
                {
                    "id": "H1",
                    "claim": "A best fits the current evidence.",
                    "supporting_evidence": ["Two records support A."],
                    "contradictory_evidence": ["One older record supports B."],
                    "assumptions": ["The supplied goal is current."],
                    "alternative_explanations": ["The older record may reflect a changed goal."],
                    "status": "supported",
                },
                {
                    "id": "H2",
                    "claim": "B may fit if the older goal still applies.",
                    "supporting_evidence": ["One older record supports B."],
                    "contradictory_evidence": ["Two current records support A."],
                    "assumptions": ["The older goal remains relevant."],
                    "alternative_explanations": ["The apparent conflict may be temporal change."],
                    "status": "weakened",
                },
            ],
            "conflicts": ["One older record supports B."],
            "alternative_explanations": ["The user's goal may have changed over time."],
            "conclusion_change_evidence": ["A current explicit statement that B is now preferred."],
            "counterfactuals": [{
                "condition": "If the current goal matched the older record",
                "expected_result": "B would receive greater support.",
                "implication": "The recommendation depends on goal recency.",
                "limitations": ["This does not prove the older goal is current."],
            }],
            "conclusion": "A is presently better supported.",
            "confidence": {"level": "medium", "score": 0.68, "basis": "Mixed traceable evidence."},
            "uncertainties": ["The goal may have changed."],
            "recommended_action": "Confirm the current goal before acting.",
            "rationale_summary": "A has broader support, but the conflict remains material.",
            "direct_causal_evidence": {"established": False, "basis": "No direct causal evidence."},
            "causal_assessment": {
                "relationship": "association",
                "supported_causal_claim": False,
                "basis": "The records co-occur but do not establish cause.",
                "limitations": ["No intervention or explicit attribution is present."],
            },
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
    assert needs_structured_reasoning("Can you do a full SWOT analysis on yourself") is True


def test_swot_selects_evidence_systems_and_uncertainty_lenses():
    names = [item["name"] for item in select_lenses("Do a full SWOT analysis on yourself")]
    assert {"evidence", "systems", "uncertainty"}.issubset(set(names))


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
    assert packet["version"] == "2.0"
    assert len(packet["hypotheses"]) == 2
    assert packet["counterfactuals"][0]["implication"]
    assert packet["conclusion_change_evidence"]
    assert packet["causal_assessment"]["relationship"] == "association"
    assert packet["causal_assessment"]["supported_causal_claim"] is False
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
    assert simple["route"]["rhee"] == "not_required"

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


def test_controller_plans_before_cognition_and_complexity_earns_systems():
    simple = plan_cognition("Hello L")
    assert simple["problem_type"] == "conversation"
    assert simple["difficulty"] == "low"
    assert simple["needs"] == {
        "memory": False,
        "external_evidence": False,
        "structured_reasoning": False,
        "longitudinal_reasoning": False,
        "specialist": False,
    }

    complex_plan = plan_cognition(
        "Deep recall my recovery pattern over time, compare the evidence and recommend what I should do"
    )
    assert complex_plan["problem_type"] == "longitudinal"
    assert complex_plan["difficulty"] == "high"
    assert complex_plan["needs"]["memory"] is True
    assert complex_plan["needs"]["structured_reasoning"] is True
    assert complex_plan["needs"]["longitudinal_reasoning"] is True


def test_controller_tracks_known_unknown_and_specialist_outcome():
    planned = plan_cognition("Search the latest research and compare the findings")
    assert "current_external_facts_until_capability_returns" in planned["unknown"]
    final = finalise_cognition_plan(
        planned,
        {},
        {"handled": True, "capability": "external_research", "status": "ok", "reply": "evidence"},
    )
    assert "specialist_result_available" in final["known"]
    assert "current_external_facts_until_capability_returns" not in final["unknown"]
    assert final["specialist"] == {"capability": "external_research", "status": "ok"}


def test_phase_two_keeps_all_confidence_dimensions_separate():
    packet = run_cognitive_core(
        "Deep recall my recovery pattern over time and assess what it means",
        {
            "context": (
                "LONG TERM RECALL ACTIVE: True\n"
                "90 | memory_recovery | ID=1 | SOURCE_ROLE=USER | PROVENANCE=linked\n"
                "80 | memory_recovery | ID=2 | SOURCE_ROLE=USER | PROVENANCE=linked\n"
                "70 | memory_recovery | ID=3 | SOURCE_ROLE=ASSISTANT | PROVENANCE=linked"
            ),
            "recall_active": True,
        },
        client=FakeClient(),
    )
    confidence = packet["confidence_dimensions"]
    assert confidence["aggregation"] == "prohibited"
    assert tuple(confidence["dimensions"]) == DIMENSIONS
    assert "overall" not in confidence
    assert confidence["dimensions"]["source"]["level"] == "high"
    assert confidence["dimensions"]["retrieval"]["level"] == "high"
    assert confidence["dimensions"]["memory"]["level"] == "high"
    assert confidence["dimensions"]["prediction"]["level"] == "not_applicable"


def test_phase_two_lowers_only_dimensions_with_missing_evidence():
    controller = plan_cognition("Deep recall why this happened and predict what will happen")
    confidence = assess_confidence_dimensions(
        "Deep recall why this happened and predict what will happen",
        controller,
        {"context": "LONG TERM RECALL ACTIVE: False", "recall_active": False},
        {"handled": False, "capability": "l_core", "status": "not_required"},
        {"active": False, "pattern_threshold_met": False},
        {"status": "degraded", "uncertainties": ["No accepted reasoning."]},
    )
    dimensions = confidence["dimensions"]
    assert dimensions["retrieval"]["level"] == "low"
    assert dimensions["memory"]["level"] == "low"
    assert dimensions["reasoning"]["level"] == "low"
    assert dimensions["prediction"]["level"] == "low"
    assert dimensions["source"]["level"] == "low"
    assert len(confidence["material_limits"]) == 5


def test_guardrails_reject_missing_or_aggregated_confidence_dimensions():
    reasoning = {
        "status": "ok",
        "evidence_summary": "evidence",
        "confidence": {"level": "medium"},
        "uncertainties": ["one limit"],
    }
    assessment = assess_cognitive_packet(
        reasoning,
        {},
        {"aggregation": "average", "dimensions": {"source": {}}},
    )
    assert "confidence_dimensions_incomplete" in assessment["issues"]
    assert "confidence_dimensions_improperly_aggregated" in assessment["issues"]


def test_phase_three_guardrails_require_competing_hypotheses_and_counterfactuals():
    packet = {
        "status": "ok",
        "evidence_summary": "One explanation was considered.",
        "confidence": {"level": "medium"},
        "uncertainties": ["Alternatives were not tested."],
        "hypotheses": [{"claim": "Only hypothesis"}],
        "counterfactuals": [],
        "conclusion_change_evidence": [],
        "causal_assessment": {"relationship": "association", "supported_causal_claim": False},
        "direct_causal_evidence": {"established": False},
    }
    assessment = assess_cognitive_packet(packet)
    assert "competing_hypotheses_missing" in assessment["issues"]
    assert "hypothesis_evidence_test_incomplete" in assessment["issues"]
    assert "counterfactual_test_missing" in assessment["issues"]
    assert "conclusion_change_test_missing" in assessment["issues"]


def test_phase_three_causal_gate_fails_closed_without_direct_evidence():
    class UnsupportedCausalCompletions(FakeCompletions):
        def create(self, **kwargs):
            response = super().create(**kwargs)
            data = json.loads(response.choices[0].message.content)
            data["causal_assessment"] = {
                "relationship": "supported_causal_claim",
                "supported_causal_claim": True,
                "basis": "A mechanism seems plausible.",
                "limitations": [],
            }
            data["direct_causal_evidence"] = {
                "established": False,
                "basis": "No explicit attribution exists.",
            }
            response.choices[0].message.content = json.dumps(data)
            return response

    client = SimpleNamespace(chat=SimpleNamespace(completions=UnsupportedCausalCompletions()))
    packet = reason("What caused this outcome?", evidence_context="association only", client=client)
    assert packet["direct_causal_evidence"]["established"] is False
    assert packet["causal_assessment"]["supported_causal_claim"] is False


def test_phase_three_causal_gate_verifies_exact_retrieved_evidence():
    class SupportedCausalCompletions(FakeCompletions):
        def create(self, **kwargs):
            response = super().create(**kwargs)
            data = json.loads(response.choices[0].message.content)
            data["causal_assessment"] = {
                "relationship": "supported_causal_claim",
                "supported_causal_claim": True,
                "basis": "Doug explicitly attributed the decision to the commute.",
                "limitations": [],
            }
            data["direct_causal_evidence"] = {
                "established": True,
                "basis": "Explicit user-authored attribution.",
                "evidence_quotes": ["I left the job because the commute was unmanageable."],
            }
            response.choices[0].message.content = json.dumps(data)
            return response

    client = SimpleNamespace(chat=SimpleNamespace(completions=SupportedCausalCompletions()))
    packet = reason(
        "Why did I leave the job?",
        evidence_context="SOURCE_ROLE=USER | I left the job because the commute was unmanageable.",
        client=client,
    )
    assert packet["direct_causal_evidence"]["established"] is True
    assert packet["direct_causal_evidence"]["verified_against_context"] is True
    assert packet["causal_assessment"]["supported_causal_claim"] is True
    assert assess_cognitive_packet(packet)["passed"] is True


def test_phase_three_packet_passes_full_governance_contract():
    packet = reason(
        "Compare the competing explanations and test what would change the conclusion",
        evidence_context="80 | memory_project_l | one\n79 | memory_project_l | two",
        client=FakeClient(),
    )
    assessment = assess_cognitive_packet(packet)
    assert assessment["passed"] is True
    assert not assessment["issues"]


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


def test_self_directed_swot_uses_project_l_architecture_contract():
    from api.server import build_architecture_audit_context

    contract = build_architecture_audit_context(
        "Can you do a full SWOT analysis on yourself",
        {"route": {"rhee": "required", "rike": "active"}},
    )
    assert "current architecture" in contract
    assert "Rhee" in contract
    assert "RIKE" in contract


def test_personal_causal_recall_contract_blocks_invented_reasons():
    from api.server import build_causal_recall_context, ensure_causal_recall_grounding

    contract = build_causal_recall_context("Why did I break up with Leah")
    assert "directly attributes" in contract
    assert "reason is not established" in contract
    assert "Context, not confirmed cause" in contract
    assert build_causal_recall_context("When did I break up with Leah") == (
        "No causal personal-history question detected."
    )
    unsafe = (
        "The reason is not documented. However, it may be connected to "
        "self-discovery and emotional understanding."
    )
    unproven = {"rike": {"direct_causal_evidence": {"established": False}}}
    grounded = ensure_causal_recall_grounding(
        "Why did I break up with Leah?", unsafe, unproven
    )
    assert "not established" in grounded
    assert "self-discovery" not in grounded

    proven = {"rike": {"direct_causal_evidence": {"established": True}}}
    assert ensure_causal_recall_grounding(
        "Why did I leave the job?", "Doug said the commute caused it.", proven
    ) == "Doug said the commute caused it."


def test_project_l_self_audit_verifier_appends_verified_runtime_status():
    from api.server import ensure_architecture_audit_grounding

    answer = ensure_architecture_audit_grounding(
        "Compare the original Project L architecture and identify contradictions",
        "A generated comparison.",
        {
            "route": {
                "rhee": "required",
                "rike": "active",
                "mary": "not_required",
                "quinn": "advisory",
            },
            "rike": {"lenses": ["systems", "decision"]},
        },
    )

    for component in ("L", "Rhee", "RIKE", "Mary", "Quinn", "Carol and Sara", "Brains Trust"):
        assert component in answer
    assert "systems, decision" in answer
    assert "recall request is not promoted" in answer
    assert "remains provisional" in answer


def test_project_l_self_audit_verifier_leaves_ordinary_answer_unchanged():
    from api.server import ensure_architecture_audit_grounding

    assert ensure_architecture_audit_grounding("Good morning L", "Morning Doug.", {}) == (
        "Morning Doug."
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


def test_pauline_report_contract_uses_calendar_window_and_current_sobriety():
    from api.server import build_pauline_report_context, pauline_report_requested

    prompt = "Can you write a full report for Pauline based on my last 6 months"
    assert pauline_report_requested(prompt) is True
    contract = build_pauline_report_context(
        prompt,
        {"iso_date": "2026-09-05"},
    )
    assert "2026-03-05 through 2026-09-05" in contract
    assert "current elapsed days: 268" in contract
    assert "chronological and thematic clinical handover" in contract
    assert "eight concrete dated or date-bounded developments" in contract
    assert "1,000–1,600 words" in contract
    assert "not a diagnosis" in contract
    assert pauline_report_requested("Write a deployment report") is False


def test_long_report_results_can_be_recovered_after_connection_drop():
    from api import server

    request_id = "86b71e80-dac5-4adc-9780-725912600983"
    server._chat_results.clear()
    server.store_chat_result(request_id, "pending")
    assert server.recover_chat_result(request_id) == {"status": "pending"}
    payload = {"reply": "Completed Pauline report", "server": "vx"}
    server.store_chat_result(request_id, "ready", payload)
    assert server.recover_chat_result(request_id) == {
        "status": "ready",
        "result": payload,
    }
    assert server.recover_chat_result("not-a-uuid") == {"status": "not_found"}


def test_pauline_report_activates_mary_and_rike():
    packet = run_cognitive_core(
        "Write a report for Pauline covering my last six months",
        {"context": "80 | memory_recovery | verified event"},
        client=FakeClient(),
    )
    assert packet["route"]["mary"] == "active"
    assert packet["route"]["rike"] == "active"
