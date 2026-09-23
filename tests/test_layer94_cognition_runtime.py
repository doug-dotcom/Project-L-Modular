"""Real stage contracts, safe fallback and persisted runtime diagnostics."""
from datetime import datetime, timezone
import json
from types import SimpleNamespace as NS

import pytest

from core.cognition import orchestrator
from core.cognition.anticipation import build_anticipation_packet
from core.cognition.longitudinal import build_longitudinal_packet


def pattern_evidence():
    day = datetime.now(timezone.utc).date().isoformat()
    return (
        f"92 | memory_health | ID=fixture1 | SOURCE_ROLE=USER | CREATED_AT={day}T00:00:00+00:00\n"
        f"{day} A simple routine helped sleep.\n"
        f"91 | memory_recovery | ID=fixture2 | SOURCE_ROLE=USER | CREATED_AT={day}T00:00:00+00:00\n"
        f"{day} A simple routine helped recovery."
    )


def test_real_mary_packet_reaches_anticipation_without_fallback():
    message = "What have you noticed across my life?"
    mary = build_longitudinal_packet(message, pattern_evidence())
    assert mary["cross_domain_support"] == 2
    assert mary["pattern_threshold_met"] is True
    packet = build_anticipation_packet(message, {}, mary, {})
    assert packet["candidates"][0]["kind"] == "current_pattern_watch"
    assert packet["candidates"][0]["confidence"] == 0.72
    assert packet["surfaceable_count"] == 0
    assert packet["governance"]["autonomous_actions"] is False


@pytest.mark.parametrize("value,expected", [
    (2, 0.72), (1, 0.66), ({"domain_count": 2}, 0.72),
    (None, 0.66), ([], 0.66), ("invalid", 0.66), (True, 0.66), (-2, 0.66),
])
def test_count_contract_preserves_legacy_and_does_not_inflate_invalid_counts(value, expected):
    mary = build_longitudinal_packet("What have you noticed across my life?", pattern_evidence())
    mary["cross_domain_support"] = value
    packet = build_anticipation_packet("Patterns", {}, mary, {})
    assert packet["candidates"][0]["confidence"] == expected


def test_full_core_completes_the_real_pattern_path():
    packet = orchestrator.run_cognitive_core(
        "What have you noticed across my life?",
        {"context": pattern_evidence(), "recall_active": True},
    )
    assert packet["runtime"]["fallback_used"] is False
    assert packet["runtime"]["status"] == "complete"
    assert packet["mary"]["cross_domain_support"] == 2
    assert packet["anticipation"]["active"] is True
    assert "learning" in packet
    # No live model was used; orchestration completion does not certify RIKE.
    assert packet["rike"]["status"] != "ok"


def test_optional_failure_preserves_context_without_leaking_exception_text(monkeypatch, caplog):
    calls = []
    def fail_anticipation(*args):
        calls.append(1)
        raise RuntimeError("private-message secret-token https://private.example")
    monkeypatch.setattr(orchestrator, "build_anticipation_packet", fail_anticipation)
    working = {"current_goal": "Finish the current task"}
    packet = orchestrator.run_cognitive_core(
        "Hello L", {"context": "private evidence", "recall_active": True},
        working_memory_packet=working,
    )
    receipt = packet["runtime"]
    assert receipt["status"] == "degraded" and receipt["fallback_used"]
    assert receipt["diagnostic"]["source_function"] == "fail_anticipation"
    assert receipt["diagnostic"]["source_file"] == "test_layer94_cognition_runtime.py"
    assert receipt["diagnostic"]["source_line"] > 0
    assert receipt["diagnostic"]["error_type"] == "RuntimeError"
    assert packet["rhee_recall_preserved"] is True
    assert packet["working_memory"] == working
    assert packet["guardrails"]["passed"] is False
    assert packet["learning"]["status"] == "not_run"
    assert calls == [1]
    for private in ("private-message", "secret-token", "https://private.example", "private evidence"):
        assert private not in json.dumps(receipt) + caplog.text


@pytest.mark.parametrize("broken_stage,provider_failure", [(False, False), (True, False), (True, True)])
def test_server_retains_runtime_receipt_in_saved_answer(monkeypatch, broken_stage, provider_failure):
    from api import server
    from core.cognition.model_independence import OpenAIChatCompletionsAdapter

    saved, prompts = [], []
    def create(**kwargs):
        prompts.append(kwargs)
        if provider_failure:
            raise RuntimeError("provider failed")
        return NS(id="layer94-fixture", model="test", choices=[NS(
            finish_reason="stop", message=NS(content="Hello Doug."))])
    client = NS(chat=NS(completions=NS(create=create)))
    monkeypatch.setattr(server, "resolve_model_adapter", lambda: OpenAIChatCompletionsAdapter(client, model_id="test"))
    monkeypatch.setattr(server, "route_capability", lambda _: {"handled": False, "status": "not_required"})
    monkeypatch.setattr(server, "write_raw_catchall", lambda role, content, **kw: {"id": 94, "role": role, "content": content})
    monkeypatch.setattr(server, "write_live_short_term", lambda *a: {"saved": False})
    monkeypatch.setattr(server, "run_brain_pipeline", lambda *a: None)
    monkeypatch.setattr(server, "voice_enabled", lambda: False)
    monkeypatch.setattr(server, "store_chat_result", lambda *args: saved.append(args))
    if broken_stage:
        def fail_anticipation(*args):
            raise ValueError("private failure content")
        monkeypatch.setattr(orchestrator, "build_anticipation_packet", fail_anticipation)
    # Run the real cognitive core through the production handler, no core mock.
    result = server.chat(server.ChatRequest(message="Hello L", conversation_id="layer94-fixture"))
    runtime = result["cognition"]["runtime"]
    assert runtime["fallback_used"] is broken_stage
    assert runtime["status"] == ("degraded" if broken_stage else "complete")
    assert saved[-1][2]["cognition"]["runtime"] == runtime
    if provider_failure:
        assert result["error"] is True
    else:
        assert result["reply"] == "Hello Doug."
    assert "private failure content" not in json.dumps(result) + json.dumps(prompts)


def test_direct_import_does_not_need_sitecustomize():
    import os
    from pathlib import Path
    import subprocess
    import sys

    root = Path(__file__).resolve().parents[1]
    # Isolated startup omits cwd/PYTHONPATH; import the app only afterwards.
    code = f"""
import sys
sys.path.insert(0, {str(root)!r})
from core.cognition import orchestrator
def fail(*args):
    raise ValueError('private')
orchestrator.build_anticipation_packet = fail
packet = orchestrator.run_cognitive_core('Hello L', {{}})
assert packet['runtime']['fallback_used'] is True
assert packet['runtime']['diagnostic']['error_type'] == 'ValueError'
"""
    result = subprocess.run([sys.executable, "-I", "-c", code], cwd="/tmp",
                            env=os.environ.copy(), capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
