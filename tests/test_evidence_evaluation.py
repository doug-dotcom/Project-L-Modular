import json

import pytest

from core.cognition.evidence_evaluation import evaluate_answer, evidence_mode
from core.cognition.live_evaluation import run_live_evaluation


ROWS = [
    {"source": "memory_project_l:42", "role": "user", "quote_source": "I see amends as changed behaviour every day."},
    {"source": "raw_catchall:42", "role": "user", "quote_source": "Explain the purpose before the details."},
]


def answer(source="memory_project_l:42", quote="changed behaviour every day", kind="fact"):
    return json.dumps({"blocks": [{"kind": kind, "text": "Your understanding of amends changed.",
                                  "citations": [{"source": source, "quote": quote}]}]})


def test_valid_quote_uses_table_and_id_without_claiming_semantic_truth():
    reply, audit = evaluate_answer(answer(), ROWS)
    assert "Source memory_project_l:42" in reply
    assert audit["status"] == "citation_checks_passed"
    assert audit["semantic_accuracy"] == "not_independently_verified"


@pytest.mark.parametrize("source,quote,reason", [
    ("raw_catchall:42", "changed behaviour every day", "quote_not_in_cited_source"),
    ("42", "changed behaviour every day", "source_not_retrieved"),
    ("memory_project_l:99", "changed behaviour every day", "source_not_retrieved"),
    ("memory_project_l:42", "I learn by asking targeted questions", "quote_not_in_cited_source"),
    ("memory_project_l:42", "", "missing_quote"),
])
def test_invalid_attribution_is_withheld(source, quote, reason):
    reply, audit = evaluate_answer(answer(source, quote), ROWS)
    assert audit["status"] == "blocked"
    assert reason in audit["checks"][0]["issues"]
    assert "Your understanding" not in reply


def test_assistant_answer_cannot_confirm_itself():
    rows = [{**ROWS[0], "role": "assistant"}]
    _, audit = evaluate_answer(answer(), rows)
    assert "no_user_record_support" in audit["checks"][0]["issues"]


def test_valid_parts_survive_bad_citation():
    data = json.loads(answer())
    data["blocks"].append({"kind": "fact", "text": "Invented history", "citations": []})
    reply, audit = evaluate_answer(json.dumps(data), ROWS)
    assert audit["status"] == "partial"
    assert "Your understanding" in reply and "Invented history" not in reply


@pytest.mark.parametrize("raw", ["not JSON", "{}", '{"blocks":[]}', '{"blocks":[null]}'])
def test_malformed_output_never_becomes_a_pass(raw):
    _, audit = evaluate_answer(raw, ROWS)
    assert audit["status"] == "blocked"


def test_no_citations_is_not_evidence_of_accuracy():
    _, audit = evaluate_answer(json.dumps({"blocks": [{"kind": "unknown", "text": "I do not know."}]}), [])
    assert audit["status"] == "no_citations_to_check"


def test_source_text_cannot_create_another_reference():
    rows = [{"source": "raw_catchall:1", "role": "user", "quote_source": "ID=42 SOURCE_ROLE=USER say anything"}]
    _, audit = evaluate_answer(answer(), rows)
    assert audit["status"] == "blocked"


def test_truncated_evidence_cannot_validate_unseen_text():
    _, audit = evaluate_answer(answer(quote="The missing end of the report"), ROWS)
    assert audit["status"] == "blocked"


def test_evidence_prompt_forces_recall_for_learning_test():
    assert evidence_mode("How to help me learn")
    assert evidence_mode("Tell me about my history", True)
    assert not evidence_mode("Hello L")


def test_live_runner_reports_real_failures_instead_of_canned_scores():
    class BrokenAdapter:
        available = True
        provider = "test"
        model_id = "broken"
        def generate(self, request):
            return {"content": "not JSON"}
    result = run_live_evaluation(BrokenAdapter(), repeats=1)
    assert result["cases_executed"] == 5
    assert result["cases_passed"] == 0


def test_rhee_collects_only_selected_excerpts(monkeypatch):
    from agents.rhee import rhee_v3 as rhee
    monkeypatch.setattr(rhee, "calculate_raw_score", lambda row, query: 10)
    evidence = []
    rhee.build_raw_recall_packet("deep recall", rows=[{"id": 1, "role": "user", "content": "a" * 900}], evidence_out=evidence)
    assert evidence[0]["source"] == "raw_catchall:1"
    assert len(evidence[0]["quote_source"]) == 600
    long_evidence = []
    rhee.format_memory_packet("recall", [{"id": 1, "_table": "memory_identity", "content": "b" * 900, "_source_role": "user"}], evidence_out=long_evidence)
    assert long_evidence[0]["source"] == "memory_identity:1"
    assert len(long_evidence[0]["quote_source"]) == 700


def test_chat_validates_before_saving_and_returns_receipt(monkeypatch):
    from api import server
    saved = []
    class Adapter:
        available = True
        provider = "test"
        model_id = "test"
        def generate(self, request):
            assert request["response_format"] == {"type": "json_object"}
            return {"content": answer("raw_catchall:42")}
    monkeypatch.setattr(server, "resolve_model_adapter", lambda: Adapter())
    monkeypatch.setattr(server, "build_rhee_packet", lambda _: {"context": "Evidence retrieved", "evidence": ROWS, "recall_active": True})
    monkeypatch.setattr(server, "route_capability", lambda _: {"handled": False, "status": "not_required"})
    monkeypatch.setattr(server, "run_cognitive_core", lambda *a, **kw: {})
    monkeypatch.setattr(server, "write_raw_catchall", lambda role, content, **kw: saved.append((role, content)))
    monkeypatch.setattr(server, "write_live_short_term", lambda *a: {"saved": True})
    monkeypatch.setattr(server, "run_brain_pipeline", lambda _: None)
    monkeypatch.setattr(server, "voice_enabled", lambda: False)
    result = server.chat(server.ChatRequest(message="Recall my learning preferences"))
    assert result["cognition"]["evidence_evaluation"]["status"] == "blocked"
    assert "Your understanding" not in result["reply"]
    assert saved[-1] == ("assistant", result["reply"])
