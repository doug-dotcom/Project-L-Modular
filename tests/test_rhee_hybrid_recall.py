import agents.rhee.rhee_v3 as rhee


def test_local_domain_library_is_loaded():
    memories = rhee.load_local_memories()
    assert len(memories) > 1000
    assert any(row.get("_table") == "local_family" for row in memories)


def test_recall_works_without_explicit_trigger(monkeypatch):
    monkeypatch.setattr(rhee, "supabase", None)
    packet = rhee.build_recall_packet("How is Luella?", limit=18)
    assert packet
    assert any("luella" in rhee.row_content(row).lower() for row in packet)


def test_unrelated_high_salience_memory_is_not_returned():
    memory = {
        "content": "A completely unrelated subject",
        "importance": 100,
        "salience": 100,
        "anchor": True,
    }
    assert rhee.calculate_memory_score(memory, "How is Luella?") == 0


def test_historical_questions_and_failed_answers_are_quarantined():
    query = "When did Luella get her braces off?"
    question = {
        "content": query,
        "primary_subject": "Luella",
        "importance": 100,
        "salience": 100,
    }
    failed = {
        "content": "The information is incomplete; there is no exact date for Luella's braces.",
        "primary_subject": "Luella",
        "importance": 100,
        "salience": 100,
    }
    explicit_save = {
        "content": "Can you remember that Luella loves netball?",
        "primary_subject": "Luella",
    }

    assert rhee.calculate_memory_score(question, query) == 0
    assert rhee.calculate_memory_score(failed, query) == 0
    assert rhee.calculate_memory_score(explicit_save, query) > 0


def test_raw_exact_query_terms_outrank_expansions():
    exact = {"content": "Luella got her braces off on 16 June 2026", "role": "user"}
    expanded = {"content": "A general story about Luella and her daughter", "role": "user"}
    query = "When did Luella get her braces off?"
    assert rhee.calculate_raw_score(exact, query) > rhee.calculate_raw_score(expanded, query)


def test_raw_matching_uses_word_boundaries_and_penalises_failed_recall():
    query = "When did Luella get her braces off?"
    fact = {
        "content": "Luella had her braces removed on 16 June 2026.",
        "role": "assistant",
    }
    failed = {
        "content": "The records do not provide an exact date for when Luella got her braces off.",
        "role": "assistant",
    }
    unrelated = {"content": "Whether there is another option", "role": "assistant"}

    assert rhee.calculate_raw_score(fact, query) > rhee.calculate_raw_score(failed, query)
    assert rhee.calculate_raw_score(unrelated, query) == 0


def test_raw_packet_puts_affirmative_dated_evidence_first(monkeypatch):
    rows = [
        {"id": 1, "content": "When did Luella get her braces off?", "role": "user"},
        {
            "id": 2,
            "content": "The information regarding when Luella got her braces off is currently incomplete.",
            "role": "assistant",
        },
        {
            "id": 3,
            "content": "Luella had her braces removed on 16 June 2026.",
            "role": "assistant",
        },
    ]
    monkeypatch.setattr(rhee, "load_all_raw_catchall", lambda: rows)
    packet = rhee.build_raw_recall_packet("When did Luella get her braces off?", limit=3)
    assert "16 June 2026" in packet
    assert "currently incomplete" not in packet


def test_context_packet_is_bounded_and_reports_recall(monkeypatch):
    monkeypatch.setattr(rhee, "supabase", None)
    packet = rhee.build_context_packet("How is Luella?")
    assert packet["recall_active"] is True
    assert "local_" in packet["context"]
    assert len(packet["context"]) < 30000
