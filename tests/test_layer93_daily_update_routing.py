"""Daily-update intake must not become a historical investigation."""
from types import SimpleNamespace as NS

import pytest

from core.cognition.controller import plan_cognition
from core.cognition.current_update import self_contained_daily_update
from core.cognition.evidence_evaluation import evidence_mode


UPDATE = (
    "Hi L, here’s my daily summary for Tuesday.\n\n"
    "I started today feeling relaxed. My intention was to get organised. "
    "I'm grateful for my kids and my recovery. I slept well when asleep, "
    "but worry about missing an appointment interrupted my night. "
    "My sleep was shorter than usual. I finished the packing and errands. "
    "I am pleased with my progress and stayed sober."
)


@pytest.mark.parametrize("message", [UPDATE, UPDATE.replace("here’s", "here is"),
    UPDATE.replace("Hi L, here’s my daily summary", "Daily update")])
def test_supplied_update_uses_current_message_without_recall(message):
    plan = plan_cognition(message)
    assert plan["signals"]["self_contained_daily_update"] is True
    assert plan["needs"]["memory"] is False
    assert plan["needs"]["cue_driven_memory"] is False
    assert plan["needs"]["longitudinal_reasoning"] is False
    assert not evidence_mode(message, plan["needs"]["memory"])


@pytest.mark.parametrize("followup", [
    "Deep recall my health history.", "Compare this with my previous reports.",
    "What do you remember about my trip?", "Please check my stored records.",
    "How has my recovery changed", "Tell me about my family.",
    "Show me supporting evidence.", "Summarise my last six months.",
])
def test_request_appended_to_update_keeps_existing_route(followup):
    assert not self_contained_daily_update(UPDATE + "\n" + followup)


@pytest.mark.parametrize("message", [
    "Here is my daily summary. I slept well.",
    "What do you remember about my Bali diving trip?",
    "Write my daily summary from yesterday's records.",
    "I am feeling proud of my recovery today.",
])
def test_short_ambiguous_and_recall_turns_do_not_take_update_shortcut(message):
    assert not self_contained_daily_update(message)


def test_explicit_deep_recall_still_requires_memory_and_evidence():
    message = UPDATE + "\nDeep recall my health history."
    plan = plan_cognition(message)
    assert plan["needs"]["memory"] is True
    assert evidence_mode(message, plan["needs"]["memory"])


def test_server_skips_historical_retrieval_but_keeps_intake_and_generation(monkeypatch):
    from api import server
    from core.cognition.model_independence import OpenAIChatCompletionsAdapter

    writes, requests, intake = [], [], []
    reply = "You got the packing done and stayed sober, Doug."
    client = NS(chat=NS(completions=NS(create=lambda **kw: NS(
        id="daily-update-fixture", model="test",
        choices=[NS(finish_reason="stop", message=NS(content=reply))]))))
    class Adapter(OpenAIChatCompletionsAdapter):
        def generate(self, request):
            requests.append(request)
            return super().generate(request)
    monkeypatch.setattr(server, "resolve_model_adapter", lambda: Adapter(client, model_id="test"))
    def unexpected_retrieval(*args, **kwargs):
        pytest.fail("Self-contained update triggered historical retrieval")
    monkeypatch.setattr(server, "build_rhee_packet", unexpected_retrieval)
    monkeypatch.setattr(server, "route_capability", lambda _: {"handled": False, "status": "not_required"})
    monkeypatch.setattr(server, "run_cognitive_core", lambda *a, **kw: {})
    def write(role, content, **kwargs):
        writes.append((role, content))
        return {"id": 93, "role": role, "content": content}
    monkeypatch.setattr(server, "write_raw_catchall", write)
    monkeypatch.setattr(server, "write_live_short_term", lambda *a: {"saved": False})
    monkeypatch.setattr(server, "run_brain_pipeline", lambda row: intake.append(row))
    monkeypatch.setattr(server, "voice_enabled", lambda: False)
    result = server.chat(server.ChatRequest(message=UPDATE))
    assert result["reply"] == reply
    assert ("user", UPDATE) in writes
    assert any(row and row["content"] == UPDATE for row in intake)
    assert any(m["role"] == "user" and m["content"] == UPDATE
               for req in requests for m in req["messages"])
    assert result["cognition"]["controller"]["needs"]["memory"] is False
