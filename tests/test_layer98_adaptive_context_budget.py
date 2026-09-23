"""Layer 98 regression tests: adaptive cognitive context budgets."""

import json
from pathlib import Path

from core.cognition.context_budget import build_generation_cognitive_context


def _controller(*, difficulty="low", **needs):
    base = {
        "memory": False,
        "current_evidence": False,
        "structured_reasoning": False,
        "longitudinal_reasoning": False,
        "specialist": False,
        "action": False,
    }
    base.update(needs)
    return {"difficulty": difficulty, "needs": base}


def test_lean_context_removes_inactive_and_separately_rendered_sections():
    packet = {
        "engine": "project_l_cognitive_core",
        "version": "13.0",
        "runtime": {"status": "complete", "fallback_used": False},
        "controller": _controller(),
        "route": {
            "rike": "not_required",
            "mary": "not_required",
            "confidence_evidence": "active",
        },
        "guardrails": {"passed": True, "issues": []},
        "confidence_dimensions": {"status": "complete", "dimensions": {"source": "medium"}},
        "confidence_evidence": {"status": "complete", "facts": ["bounded"]},
        "rike": {"status": "not_required", "large": "x" * 5000},
        "mary": {"active": False, "large": "x" * 5000},
        "working_memory": {"private": "current operational thread"},
        "model_independence": {"provider": "replaceable"},
        "portability": {"status": "available"},
    }

    result = build_generation_cognitive_context(packet)
    rendered = json.loads(result["context"])
    receipt = result["receipt"]

    assert receipt["mode"] == "lean"
    assert "confidence_evidence" in rendered
    assert "rike" not in rendered
    assert "mary" not in rendered
    assert "controller" not in rendered
    assert "working_memory" not in rendered
    assert "model_independence" not in rendered
    assert "portability" not in rendered
    assert receipt["rendered_chars"] < receipt["full_packet_chars"]
    assert receipt["rhee_evidence_modified"] is False
    assert receipt["stored_cognitive_packet_modified"] is False


def test_structured_reasoning_preserves_active_reasoning_and_pattern_sections():
    packet = {
        "engine": "project_l_cognitive_core",
        "version": "13.0",
        "runtime": {"status": "complete", "fallback_used": False},
        "controller": _controller(
            difficulty="high",
            memory=True,
            structured_reasoning=True,
            longitudinal_reasoning=True,
        ),
        "route": {
            "rike": "active",
            "mary": "active",
            "quinn": "advisory",
            "memory_identity": "current_identity_prioritised",
            "memory_counterexample": "checked",
            "confidence_evidence": "active",
        },
        "guardrails": {"passed": True, "issues": []},
        "confidence_dimensions": {"status": "complete"},
        "confidence_evidence": {"status": "complete", "basis": "retrieved evidence"},
        "rike": {"status": "complete", "conclusion": "bounded inference"},
        "mary": {"active": True, "patterns": [{"status": "developing"}]},
        "quinn": {"status": "complete", "principles": ["advisory only"]},
        "memory_identity": {"active": True, "decision": "current_identity_prioritised"},
        "memory_counterexample": {"active": True, "decision": "checked"},
        "working_memory": {"current_goal": "answer accurately"},
        "model_independence": {"provider": "replaceable"},
    }

    result = build_generation_cognitive_context(packet, evidence_required=True)
    rendered = json.loads(result["context"])
    receipt = result["receipt"]

    assert receipt["mode"] == "expanded"
    for key in (
        "rike",
        "mary",
        "quinn",
        "confidence_evidence",
        "memory_identity",
        "memory_counterexample",
    ):
        assert key in rendered
    assert receipt["required_context_preserved"] is True
    assert receipt["rhee_evidence_modified"] is False


def test_evidence_requirement_alone_expands_context_without_copying_evidence():
    packet = {
        "engine": "project_l_cognitive_core",
        "version": "13.0",
        "runtime": {"status": "complete", "fallback_used": False},
        "controller": _controller(),
        "route": {"rike": "not_required"},
        "guardrails": {"passed": True, "issues": []},
        "rike": {"status": "not_required"},
        "mary": {"active": False},
        "quinn": {"status": "not_required"},
        "confidence_evidence": {"status": "complete"},
    }

    result = build_generation_cognitive_context(packet, evidence_required=True)

    assert result["receipt"]["mode"] == "expanded"
    assert result["receipt"]["rhee_evidence_modified"] is False
    assert "evidence" not in result["receipt"]


def test_receipt_contains_structure_and_sizes_not_omitted_private_values():
    private = "PRIVATE-NARRATIVE-SHOULD-NOT-ENTER-RECEIPT"
    packet = {
        "engine": "project_l_cognitive_core",
        "version": "13.0",
        "runtime": {"status": "complete", "fallback_used": False},
        "controller": _controller(),
        "route": {"rike": "not_required"},
        "guardrails": {"passed": True, "issues": []},
        "working_memory": {"temporary_assumption": private},
        "model_independence": {"debug": private},
        "portability": {"bootstrap": private},
    }

    result = build_generation_cognitive_context(packet)
    receipt_text = json.dumps(result["receipt"], sort_keys=True)

    assert private not in result["context"]
    assert private not in receipt_text
    assert set(result["receipt"]["separately_rendered_sections"]) >= {
        "controller",
        "working_memory",
        "model_independence",
        "portability",
    }


def test_server_builds_budget_before_prompt_and_retains_receipt_in_cognition():
    source = Path("api/server.py").read_text(encoding="utf-8")

    call = source.index("generation_context = build_generation_cognitive_context(")
    prompt = source.index('        system_prompt = f"""', call)
    receipt = source.index('cognitive_packet["context_budget"] = generation_context["receipt"]', call)

    assert call < receipt < prompt
    assert "COGNITIVE CONTEXT BUDGET:" in source
    assert "evidence_required=check_evidence" in source
