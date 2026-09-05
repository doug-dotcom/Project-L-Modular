from threading import Event

from core.cognition.multi_agent import (
    WORKER_REGISTRY,
    build_multi_agent_packet,
    run_parallel_foundation,
)
from core.cognition.orchestrator import run_cognitive_core


def test_phase_nine_registry_contains_canonical_workers():
    assert {"rhee", "mary", "rike", "carol", "sara", "quinn", "fiona"}.issubset(
        WORKER_REGISTRY
    )
    for spec in WORKER_REGISTRY.values():
        assert spec["role"]
        assert spec["phase"]
        assert isinstance(spec["dependencies"], list)


def test_phase_nine_independent_workers_execute_concurrently():
    mary_started = Event()
    quinn_started = Event()

    def mary_builder(_message, _context):
        mary_started.set()
        assert quinn_started.wait(0.5)
        return {"engine": "mary", "active": True, "status": "ok"}

    def quinn_builder(_message):
        quinn_started.set()
        assert mary_started.wait(0.5)
        return {"engine": "quinn", "status": "ok", "principles": []}

    packet = run_parallel_foundation(
        "Compare this pattern over time",
        "traceable evidence",
        structured_reasoning_required=True,
        mary_builder=mary_builder,
        quinn_builder=quinn_builder,
    )
    assert packet["parallel_execution"] is True
    assert packet["receipts"]["mary"]["status"] == "complete"
    assert packet["receipts"]["quinn"]["status"] == "complete"


def test_phase_nine_worker_failure_is_isolated_and_visible():
    def broken_mary(_message, _context):
        raise RuntimeError("deliberate worker failure")

    foundation = run_parallel_foundation(
        "Assess this pattern over time",
        "traceable evidence",
        structured_reasoning_required=True,
        mary_builder=broken_mary,
        quinn_builder=lambda _message: {
            "engine": "quinn", "status": "ok", "principles": []
        },
    )
    packet = build_multi_agent_packet(
        {"needs": {"memory": True}},
        {"recall_active": True},
        {"handled": False, "capability": "l_core", "status": "not_required"},
        foundation,
        {"status": "not_required"},
    )
    assert foundation["receipts"]["mary"]["status"] == "error"
    assert foundation["receipts"]["quinn"]["status"] == "complete"
    assert packet["status"] == "degraded"
    assert packet["required_failures"] == ["mary"]


def test_phase_nine_enforces_one_l_and_zero_worker_authority():
    foundation = run_parallel_foundation(
        "Compare this pattern over time",
        "traceable evidence",
        structured_reasoning_required=True,
    )
    packet = build_multi_agent_packet(
        {"needs": {"memory": True}},
        {"recall_active": True},
        {"handled": False, "capability": "l_core", "status": "not_required"},
        foundation,
        {"status": "ok"},
    )
    assert packet["user_facing_voice"] == "L"
    assert packet["synthesis_owner"] == "L"
    assert packet["one_voice"] is True
    assert packet["governance"]["passed"] is True
    assert all(not worker["voice_authority"] for worker in packet["workers"].values())
    assert all(not worker["decision_authority"] for worker in packet["workers"].values())


def test_phase_nine_routes_fiona_only_for_financial_intelligence():
    foundation = run_parallel_foundation(
        "Review these uploaded transactions",
        "",
        structured_reasoning_required=False,
    )
    packet = build_multi_agent_packet(
        {"needs": {"memory": False}},
        {},
        {"handled": True, "capability": "financial_intelligence", "status": "ok"},
        foundation,
        {"status": "not_required"},
    )
    assert packet["workers"]["fiona"]["invoked"] is True
    assert packet["workers"]["fiona"]["status"] == "ok"
    assert packet["workers"]["deterministic_services"]["invoked"] is False


def test_phase_nine_cognitive_core_exposes_governed_worker_packet():
    packet = run_cognitive_core(
        "Hello L",
        {"context": "", "recall_active": False},
        capability_packet={},
        client=None,
    )
    assert packet["version"] == "12.0"
    assert packet["multi_agent"]["one_voice"] is True
    assert packet["multi_agent"]["synthesis_owner"] == "L"
    assert packet["multi_agent"]["governance"]["passed"] is True
    assert packet["multi_agent"]["parallel_execution"] is False


def test_phase_nine_live_server_contract_is_wired():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "api" / "server.py").read_text(encoding="utf-8")
    assert '"version": "12.0"' in source
    assert '"multi_agent": "governed_multi_agent_cognition_v1"' in source
    assert '"one_l_multiple_bounded_workers": True' in source
    assert '"multi_agent": cognitive_packet.get("multi_agent", {})' in source
