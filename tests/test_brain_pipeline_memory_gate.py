from pathlib import Path

from memory.promotion.gate import evaluate_promotion, should_store_memory


def decision(content, role="user", raw_id=101):
    return evaluate_promotion({"id": raw_id, "role": role, "content": content})


def test_questions_and_recall_requests_do_not_pollute_long_term_memory():
    assert decision("When did Luella get her braces off?")["reason"] == "question_or_recall"
    assert decision("How is Luella?")["promote"] is False
    assert decision("Do you remember when we fixed Rhee")["promote"] is False


def test_explicit_memory_instruction_is_preserved_even_as_question():
    assert decision("Can you remember that Luella loves netball?") == {
        "promote": True,
        "reason": "explicit_save_instruction",
        "explicit": True,
    }
    assert should_store_memory("Please mark today as the day Luella got her braces off") is True
    assert should_store_memory("Remember that I smoke") is True


def test_negated_memory_instruction_is_not_misread_as_a_save_request():
    result = decision("Please do not save this conversation")
    assert result["promote"] is False
    assert result["reason"] == "persistence_negated"
    assert decision("Please save the report as a PDF")["reason"] == "operational_request"


def test_only_doug_authored_rows_can_auto_promote():
    result = decision("Doug prefers direct evidence over inference.", role="assistant")
    assert result["promote"] is False
    assert result["reason"] == "untrusted_source_role"


def test_greetings_acknowledgements_and_operational_requests_stay_short_term():
    rejected = {
        "Good night L": "greeting",
        "Awesome thanks sister": "acknowledgement",
        "Hey L are you there": "greeting",
        "Please audit L again": "operational_request",
        "Fix the memory gate": "operational_request",
    }
    for content, reason in rejected.items():
        assert decision(content)["reason"] == reason


def test_pasted_assistant_transcript_is_not_treated_as_doug_authored_truth():
    result = decision("Yes, Doug — I checked Supabase and found several records.")
    assert result["promote"] is False
    assert result["reason"] == "assistant_transcript"
    assert decision("Yes — absolutely. We can use the same approach again.")["reason"] == "conversational_reply"


def test_substantive_statements_still_auto_promote():
    durable = [
        "I started Project L in June 2026.",
        "Action matters more than certainty.",
        "Today I completed my first tropical dive.",
        "My preferred learning style starts with context and then terminology.",
    ]
    for content in durable:
        assert decision(content) == {
            "promote": True,
            "reason": "durable_statement",
            "explicit": False,
        }


def test_malformed_rows_fail_closed():
    assert evaluate_promotion(None)["reason"] == "invalid_row"
    assert decision("A valid statement without an id.", raw_id=None)["reason"] == "missing_raw_id"
    assert decision("Ok")["reason"] == "too_short"


def test_legacy_carol_entrypoints_delegate_to_the_canonical_gate():
    root = Path(__file__).resolve().parents[1]
    domains = ("health", "identity", "project_l", "recovery", "relationships", "sport", "work")
    for domain in domains:
        source = (root / "agents" / "carol" / f"carol_{domain}.py").read_text(encoding="utf-8")
        assert "from agents.carol.carol import process_domain" in source
        assert "return process_domain(SOURCE_TABLE, TARGET_TABLE, limit=limit)" in source
        assert ".insert(" not in source
