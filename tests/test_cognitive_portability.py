import json

from core.cognition.portability import (
    RECONSTRUCTION_FIELDS,
    build_clean_model_request,
    build_cognitive_bootstrap,
    evaluate_reconstruction,
    portability_manifest,
    run_portability_certification,
)


def valid_reconstruction():
    result = {
        field: {
            "summary": f"Bootstrap-grounded reconstruction of {field}.",
            "evidence_refs": ["memory:5477"],
        }
        for field in RECONSTRUCTION_FIELDS
    }
    result["who_l_is"]["evidence_refs"] = ["runtime:l_identity"]
    result["communication_rules"]["evidence_refs"] = ["runtime:communication"]
    result["current_vs_superseded_patterns"]["evidence_refs"] = ["runtime:pattern_lifecycle"]
    result["deep_recall_behaviour"].update({
        "evidence_refs": ["runtime:deep_recall"],
        "supabase_first": True,
        "asks_user_to_repeat_retrievable_facts": False,
    })
    result["inference_boundaries"].update({
        "evidence_refs": ["runtime:inference_boundaries"],
        "facts_separated_from_inference": True,
        "unsupported_claims_prohibited": True,
    })
    return result


class CleanFixtureAdapter:
    available = True
    provider = "clean-fixture"
    model_id = "zero-context-model"

    def __init__(self, reconstruction=None):
        self.reconstruction = reconstruction or valid_reconstruction()
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return {"status": "complete", "content": json.dumps(self.reconstruction)}


def test_phase_twelve_bootstrap_contains_only_governed_input_and_traceable_refs():
    bootstrap = build_cognitive_bootstrap(
        "90 | memory_project_l | ID=5477 | SOURCE_ROLE=USER\nPhase 12 contract"
    )
    assert bootstrap["model_prior_context"] is False
    assert bootstrap["only_permitted_input"] == "this_bootstrap"
    assert "memory:5477" in bootstrap["permitted_evidence_references"]
    assert set(bootstrap["reconstruction_schema"]) == set(RECONSTRUCTION_FIELDS)
    assert bootstrap["bootstrap_fingerprint"]


def test_phase_twelve_clean_request_has_no_conversation_history_or_hidden_context():
    bootstrap = build_cognitive_bootstrap("ID=5477 evidence")
    request = build_clean_model_request(bootstrap)
    assert request["purpose"] == "cognitive_portability_certification"
    assert request["temperature"] == 0.0
    assert request["response_format"] == {"type": "json_object"}
    assert len(request["messages"]) == 2
    assert "zero prior Doug context" in request["messages"][0]["content"]
    assert json.loads(request["messages"][1]["content"])["bootstrap_fingerprint"]


def test_phase_twelve_clean_model_reconstructs_all_nine_domains_from_bootstrap():
    bootstrap = build_cognitive_bootstrap("ID=5477 portable evidence")
    adapter = CleanFixtureAdapter()
    receipt = run_portability_certification(adapter, bootstrap)
    assert receipt["status"] == "passed"
    assert receipt["passed"] is True
    assert receipt["model_receipt"]["prior_context_supplied"] is False
    assert receipt["model_receipt"]["input_boundary"] == "bootstrap_only"
    assert receipt["evaluation"]["score"] == {"passed": 14, "total": 14}
    assert all(item["passed"] for item in receipt["evaluation"]["field_checks"].values())
    assert set(receipt["reconstruction"]) == set(RECONSTRUCTION_FIELDS)


def test_phase_twelve_fails_closed_for_untraceable_or_missing_reconstruction():
    bootstrap = build_cognitive_bootstrap("ID=5477 portable evidence")
    reconstruction = valid_reconstruction()
    reconstruction.pop("recent_changes")
    reconstruction["who_doug_is"]["evidence_refs"] = ["memory:invented"]
    evaluation = evaluate_reconstruction(bootstrap, reconstruction)
    assert evaluation["status"] == "failed"
    assert evaluation["field_checks"]["recent_changes"]["complete"] is False
    assert evaluation["field_checks"]["who_doug_is"]["traceable"] is False


def test_phase_twelve_fails_closed_when_deep_recall_or_inference_rules_drift():
    bootstrap = build_cognitive_bootstrap("ID=5477 portable evidence")
    reconstruction = valid_reconstruction()
    reconstruction["deep_recall_behaviour"]["supabase_first"] = False
    reconstruction["inference_boundaries"]["unsupported_claims_prohibited"] = False
    evaluation = evaluate_reconstruction(bootstrap, reconstruction)
    assert evaluation["passed"] is False
    assert evaluation["governance_checks"]["supabase_first"] is False
    assert evaluation["governance_checks"]["unsupported_claims_prohibited"] is False


def test_phase_twelve_manifest_and_live_server_contract_are_wired():
    from pathlib import Path

    manifest = portability_manifest()
    server = (Path(__file__).resolve().parents[1] / "api" / "server.py").read_text(encoding="utf-8")
    assert manifest["clean_model_prior_context"] is False
    assert manifest["input_boundary"] == "bootstrap_only"
    assert '"version": "13.0"' in server
    assert '@app.get("/cognition/portability-certification")' in server
    assert '"portability": "cognitive_portability_certification_v1"' in server
    assert '"clean_model_receives_bootstrap_only": True' in server


def test_phase_twelve_endpoint_executes_clean_certification_without_exposing_evidence(monkeypatch):
    import api.server as server

    adapter = CleanFixtureAdapter()
    monkeypatch.setattr(server, "resolve_model_adapter", lambda: adapter)
    monkeypatch.setattr(
        server,
        "build_rhee_packet",
        lambda query: {
            "version": "v5.0",
            "deep_recall": True,
            "context_size": 42,
            "context": "90 | memory_project_l | ID=5477 | SOURCE_ROLE=USER\nPortable evidence",
        },
    )
    receipt = server.cognition_portability_certification()
    assert receipt["passed"] is True
    assert receipt["bootstrap_receipt"]["deep_recall"] is True
    assert receipt["bootstrap_receipt"]["persistent_evidence_exposed"] is False
    assert receipt["reconstruction_exposed"] is False
    assert "reconstruction" not in receipt
    assert receipt["model_receipt"]["prior_context_supplied"] is False
