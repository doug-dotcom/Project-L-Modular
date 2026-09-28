from services.shine_ai_trace_verifier import verify_decision_trace


def response_fixture():
    contract = "a" * 64
    return {
        "response_profile_contract_sha256": contract,
        "planning": {
            "version": 1,
            "tool_source": "server",
            "selected_tools": ["calculator"],
            "memory_source": "server",
            "selected_memory": {"project-l": ["sport", "episodic"]},
            "route": "model",
            "provider": "fake",
            "model": "fake-fast",
            "model_tier": "fast",
            "routing_score": 0,
            "max_output_tokens": 600,
            "context_budget_chars": 4000,
            "context_budget_items": 5,
            "deferred_controls": ["context-selection", "request-cost"],
            "reasons": ["Private server prose is not attested."],
        },
        "recovery": {
            "version": 1,
            "mode": "not-needed",
            "failure_stage": None,
            "action": "none",
            "automatic_retry_count": 0,
            "reason": "Private recovery prose.",
        },
        "execution": {
            "version": 1,
            "status": "adjusted",
            "route": "model",
            "provider": "fake",
            "model": "fake-fast-2026-09-28",
            "model_tier": "fast",
            "max_output_tokens": 200,
            "tools": ["calculator"],
            "memory": {"project-l": ["episodic", "sport"]},
            "context_budget_chars": 4000,
            "context_budget_items": 5,
            "adjustments": [
                "provider-resolved-model",
                "output-token-tightened",
            ],
        },
        "grounding": {
            "evidence_available": True,
            "selected_evidence_ids": ["memory:project-l:PRIVATE"],
            "cited_evidence_ids": ["memory:project-l:PRIVATE"],
            "unknown_citation_ids": [],
            "citation_coverage": 1.0,
        },
        "verification": {
            "mode": "verified",
            "evidence_required": True,
            "evidence_available": True,
            "cited_evidence_count": 1,
            "unknown_citation_count": 0,
            "required_memory_sources": ["project-l"],
            "cited_memory_sources": ["project-l"],
            "required_tool_request_ids": ["PRIVATE-TOOL-ID"],
            "cited_tool_request_ids": ["PRIVATE-TOOL-ID"],
            "warnings": [],
        },
        "delivery": {
            "mode": "normal",
            "reason": "Private delivery prose.",
        },
        "decision_trace": {
            "version": 1,
            "algorithm": "sha256",
            "scope": "control-plane",
            "service_version": "1.37.0",
            "service_release": "1.37.0+git.abcdef123456",
            "response_profile_contract_sha256": contract,
            "planning_sha256": "68d464a80cd82787eb5c5391d86e4a9b7dc477f67d3d4bb82ee596cdd8c93f9d",
            "recovery_sha256": "c690b4050317e031dab631f91e4832e9da49b0b8e02ad9d16288a4f76e0af44d",
            "execution_sha256": "063db9b91b9c8a6878066453a499b98202a21b7ce4972e0ec1b2bce5c49f3d36",
            "grounding_sha256": "ca6fc17368ae4d4afae24d5dcfc62e6d3f1021c5b800ac211c1c864efd5ba48a",
            "verification_sha256": "b5c8fbc43fe35b5fb30affdddfa2cb61716666f5b2d1f796a0b66f314359297e",
            "delivery_sha256": "fa76e6a145e80d3ef8d955abd5a17426feba569df832d2cf6af7dbd5b86c5240",
            "lineage_sha256": "9b22f32294c8ab531135a1c7d3326d470d11024f6b8a7a066bff67b0a1d944ff",
        },
    }


def test_independent_verifier_matches_shine_ai_golden_vector():
    result = verify_decision_trace(
        response_fixture(),
        header_version="1.37.0",
        header_release="1.37.0+git.abcdef123456",
    )

    assert result["status"] == "verified"
    assert result["verified"] is True
    assert result["lineage_sha256"] == (
        "9b22f32294c8ab531135a1c7d3326d470d11024f6b8a7a066bff67b0a1d944ff"
    )


def test_independent_verifier_detects_control_plane_tampering():
    payload = response_fixture()
    payload["execution"]["max_output_tokens"] = 201

    result = verify_decision_trace(payload)

    assert result["status"] == "invalid"
    assert result["verified"] is False
    assert result["reason_code"] == "decision-trace-digest-mismatch"
    assert result["recomputed_lineage_sha256"] != result["lineage_sha256"]


def test_independent_verifier_binds_service_headers():
    result = verify_decision_trace(
        response_fixture(),
        header_version="1.38.0",
        header_release="1.37.0+git.abcdef123456",
    )

    assert result["status"] == "invalid"
    assert result["reason_code"] == "decision-trace-version-header-mismatch"


def test_private_evidence_ids_do_not_affect_verified_trace():
    payload = response_fixture()
    payload["grounding"]["selected_evidence_ids"] = ["memory:project-l:OTHER-PRIVATE"]
    payload["grounding"]["cited_evidence_ids"] = ["memory:project-l:OTHER-PRIVATE"]
    payload["verification"]["required_tool_request_ids"] = ["OTHER-PRIVATE-TOOL"]
    payload["verification"]["cited_tool_request_ids"] = ["OTHER-PRIVATE-TOOL"]

    result = verify_decision_trace(payload)

    assert result["status"] == "verified"
    assert result["verified"] is True



def test_live_verifier_requires_response_identity_headers():
    result = verify_decision_trace(
        response_fixture(),
        require_response_identity=True,
    )

    assert result["status"] == "invalid"
    assert result["reason_code"] == "decision-trace-response-identity-missing"
