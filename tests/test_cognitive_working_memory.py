from datetime import datetime, timedelta, timezone

from core.cognition.orchestrator import run_cognitive_core
from core.cognition.working_memory import ActiveContextService, MAX_ITEMS


NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)


def test_phase_ten_tracks_all_canonical_active_state_fields():
    service = ActiveContextService()
    packet = service.begin_turn(
        "doug",
        "Doug approved deployment. How do we complete Project L Phase 10?",
        {"problem_type": "implementation"},
        {"recall_active": True, "deep_recall": True, "context": "record:5477"},
        {"handled": True, "capability": "l_core", "status": "ok"},
        request_id="phase-10",
        now=NOW,
    )
    assert packet["current_goal"]
    assert packet["active_task"] == "implementation"
    assert "Doug" in packet["active_entities"]
    assert packet["recent_decisions"]
    assert packet["unresolved_questions"]
    assert packet["temporary_assumptions"] == []
    assert packet["conversation_phase"] == "execution"
    assert {item["packet"] for item in packet["active_evidence_packets"]} == {
        "rhee", "capability"
    }


def test_phase_ten_is_disposable_bounded_and_has_no_persistence_path():
    service = ActiveContextService(ttl_seconds=60)
    packet = {}
    for index in range(MAX_ITEMS + 5):
        packet = service.begin_turn(
            "doug",
            f"I decided option {index} for now",
            {"problem_type": "decision"},
            {},
            {},
            now=NOW,
        )
    assert len(packet["recent_decisions"]) == MAX_ITEMS
    assert len(packet["temporary_assumptions"]) == MAX_ITEMS
    assert packet["governance"]["durable"] is False
    assert packet["governance"]["rebuildable"] is True
    assert packet["governance"]["storage"] == "process_memory_only"
    assert packet["governance"]["database_writes"] == 0
    assert packet["governance"]["automatic_promotion"] is False
    assert service.snapshot("doug", now=NOW + timedelta(seconds=61)) == {}


def test_phase_ten_preserves_goal_across_continuation_and_resolves_answered_question():
    service = ActiveContextService()
    first = service.begin_turn(
        "doug",
        "Build Project L working memory?",
        {"problem_type": "implementation"},
        {},
        {},
        now=NOW,
    )
    continued = service.begin_turn(
        "doug",
        "Authorised 👍",
        {"problem_type": "execution"},
        {},
        {},
        now=NOW,
    )
    completed = service.complete_turn("doug", "Phase 10 is complete.", now=NOW)
    assert continued["current_goal"] == first["current_goal"]
    assert continued["generation"] == 2
    assert completed["unresolved_questions"] == []


def test_phase_ten_stores_evidence_receipts_not_evidence_content():
    service = ActiveContextService()
    packet = service.begin_turn(
        "doug",
        "Recall the current task",
        {"problem_type": "recall"},
        {"recall_active": True, "context": "sensitive evidence content"},
        {},
        now=NOW,
    )
    receipt = packet["active_evidence_packets"][0]
    assert receipt["context_size"] == len("sensitive evidence content")
    assert receipt["content_digest"]
    assert "sensitive evidence content" not in str(packet)
    assert packet["governance"]["evidence_content_stored"] is False


def test_phase_ten_cognitive_core_exposes_working_memory_packet():
    working_memory = {"engine": "cognitive_working_memory", "status": "active"}
    packet = run_cognitive_core(
        "Hello L",
        {"context": "", "recall_active": False},
        capability_packet={},
        client=None,
        working_memory_packet=working_memory,
    )
    assert packet["version"] == "12.0"
    assert packet["working_memory"] == working_memory


def test_phase_ten_live_server_contract_is_wired():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "api" / "server.py").read_text(encoding="utf-8")
    assert '"version": "12.0"' in source
    assert '"working_memory": "cognitive_working_memory_v1"' in source
    assert '"working_memory_is_disposable_and_rebuildable": True' in source
    assert "active_context_service.begin_turn(" in source
    assert "active_context_service.complete_turn(" in source
    assert '"working_memory": cognitive_packet.get("working_memory", {})' in source
