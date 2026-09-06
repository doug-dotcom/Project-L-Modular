import agents.rhee.rhee_v3 as rhee
from memory.retrieval.cache_state import (
    cache_generation,
    invalidate_recall_caches,
)


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


def test_specialised_rows_expose_dates_and_anchor_keys_to_recall():
    episode = {
        "_table": "episodic_memories",
        "event_date": "2026-06-16",
        "summary": "Luella got her braces off.",
    }
    anchor = {
        "_table": "identity_anchors",
        "key": "learning_style:raw_88",
        "value": "My preferred learning style starts with context.",
    }

    assert rhee.row_content(episode) == "2026-06-16 — Luella got her braces off."
    assert rhee.row_content(anchor).startswith("learning_style:raw_88:")
    assert rhee.calculate_memory_score(episode, "Luella braces 2026") > 0


def test_long_term_cache_refreshes_immediately_after_invalidation(monkeypatch):
    source_rows = [{"content": "First durable fact", "role": "user"}]
    monkeypatch.setattr(rhee, "LONG_TERM_TABLES", ["memory_general"])
    monkeypatch.setattr(rhee, "load_local_memories", lambda: [])
    monkeypatch.setattr(rhee, "load_table_memories", lambda table: [dict(row) for row in source_rows])
    monkeypatch.setattr(rhee, "load_all_raw_catchall", lambda: [])
    monkeypatch.setattr(
        rhee,
        "_memory_cache",
        {"loaded_at": 0.0, "rows": None, "generation": cache_generation("long_term")},
    )

    first = rhee.load_all_memories()
    source_rows.append({"content": "Newly saved durable fact", "role": "user"})
    still_cached = rhee.load_all_memories()
    invalidate_recall_caches(long_term=True)
    refreshed = rhee.load_all_memories()

    assert len(first) == 1
    assert len(still_cached) == 1
    assert len(refreshed) == 2
    assert any("Newly saved" in row["content"] for row in refreshed)


def test_raw_cache_refreshes_immediately_after_invalidation(monkeypatch):
    source_rows = [{"id": 1, "role": "user", "content": "First raw fact"}]

    class RawQuery:
        def select(self, *args, **kwargs):
            return self

        def order(self, *args, **kwargs):
            return self

        def range(self, *args, **kwargs):
            return self

        def execute(self):
            return type("Response", (), {"data": [dict(row) for row in source_rows]})()

    class RawClient:
        def table(self, table_name):
            assert table_name == "raw_catchall"
            return RawQuery()

    monkeypatch.setattr(rhee, "supabase", RawClient())
    monkeypatch.setattr(
        rhee,
        "_raw_cache",
        {"loaded_at": 0.0, "rows": None, "generation": cache_generation("raw")},
    )

    first = rhee.load_all_raw_catchall()
    source_rows.append({"id": 2, "role": "user", "content": "Newly saved raw fact"})
    still_cached = rhee.load_all_raw_catchall()
    invalidate_recall_caches(raw=True)
    refreshed = rhee.load_all_raw_catchall()

    assert len(first) == 1
    assert len(still_cached) == 1
    assert len(refreshed) == 2
    assert refreshed[-1]["id"] == 2


def test_doug_authored_memory_outranks_equivalent_assistant_memory():
    base = {
        "content": "Luella got her braces off on 16 June 2026.",
        "primary_subject": "Luella",
        "importance": 70,
        "salience": 70,
    }
    user_memory = {**base, "_source_role": "user"}
    assistant_memory = {**base, "_source_role": "assistant"}

    user_score = rhee.calculate_memory_score(user_memory, "When did Luella get her braces off?")
    assistant_score = rhee.calculate_memory_score(assistant_memory, "When did Luella get her braces off?")

    assert user_score > assistant_score > 0


def test_raw_doug_record_outranks_equivalent_assistant_record():
    query = "When did Luella get her braces off?"
    content = "Luella got her braces off on 16 June 2026."

    user_score = rhee.calculate_raw_score({"content": content, "role": "user"}, query)
    assistant_score = rhee.calculate_raw_score({"content": content, "role": "assistant"}, query)

    assert user_score > assistant_score > 0


def test_duplicate_memory_prefers_doug_authored_provenance(monkeypatch):
    monkeypatch.setattr(rhee, "LONG_TERM_TABLES", ["memory_family"])
    monkeypatch.setattr(
        rhee,
        "load_local_memories",
        lambda: [{"content": "Doug's direct fact", "role": "user", "_table": "local_family"}],
    )
    monkeypatch.setattr(
        rhee,
        "load_table_memories",
        lambda table: [{"content": "Doug's direct fact", "raw_id": 44}],
    )
    monkeypatch.setattr(
        rhee,
        "load_all_raw_catchall",
        lambda: [{"id": 44, "role": "assistant"}],
    )
    monkeypatch.setattr(rhee, "_memory_cache", {"loaded_at": 0.0, "rows": None})

    memories = rhee.load_all_memories()

    assert len(memories) == 1
    assert memories[0]["_table"] == "local_family"
    assert memories[0]["_source_role"] == "user"


def test_formatted_packet_exposes_provenance_to_reasoning_layer():
    packet = [{
        "content": "Doug's direct fact",
        "_score": 300,
        "_table": "memory_family",
        "_source_role": "user",
        "_provenance_evidence": "raw_catchall",
    }]

    context = rhee.format_memory_packet("fact", packet)

    assert "USER records are Doug-authored primary evidence" in context
    assert "SOURCE_ROLE=USER" in context
    assert "PROVENANCE=raw_catchall" in context


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


def test_quarantine_status_and_oversized_composites_are_not_recalled():
    query = "Project L memory"
    quarantined = {
        "content": "Project L memory is operational.",
        "memory_status": "QUARANTINED",
    }
    oversized = {
        "content": "Project L memory " + ("archive " * 3000),
        "memory_status": "ACTIVE",
    }

    assert rhee.calculate_memory_score(quarantined, query) == 0
    assert rhee.calculate_memory_score(oversized, query) == 0


def test_raw_historical_artifacts_are_excluded_not_merely_downranked():
    query = "When was the exact date for Project L?"
    question = {"content": query, "role": "user"}
    failed = {
        "content": "The records are incomplete and do not provide an exact date for Project L.",
        "role": "assistant",
    }

    assert rhee.calculate_raw_score(question, query) == 0
    assert rhee.calculate_raw_score(failed, query) == 0


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
    # Stage 5 live entry must fail closed, not silently scan a stale offline corpus.
    assert packet['recall_plan']['status'] == 'unavailable'
    assert packet["recall_active"] is False
    assert "Indexed recall unavailable" in packet["context"]
    assert len(packet["context"]) < 30000


def test_indexed_search_fetches_bounded_candidates_in_one_rpc(monkeypatch):
    calls = []

    class RpcQuery:
        def execute(self):
            return type("Response", (), {"data": {
                "raw": [{"id": 7, "role": "user", "content": "Luella braces"}],
                "memories": [{
                    "id": 8,
                    "content": "Luella got her braces off.",
                    "_table": "memory_family",
                    "_source_role": "user",
                    "_provenance_evidence": "raw_catchall",
                }],
            }})()

    class RpcClient:
        def rpc(self, name, params):
            calls.append((name, params))
            return RpcQuery()

    monkeypatch.setattr(rhee, "supabase", RpcClient())
    result = rhee.search_database_candidates("When did Luella get her braces off?")

    assert len(calls) == 1
    assert calls[0][0] == "search_project_l_memory"
    assert calls[0][1]["p_raw_limit"] == 200
    assert calls[0][1]["p_memory_limit"] == 80
    assert {"luella", "braces"}.issubset(set(calls[0][1]["p_terms"]))
    assert result["raw"][0]["id"] == 7
    assert result["memories"][0]["_source_role"] == "user"


def test_recall_is_not_misread_as_all_or_evidence_mode():
    prompt = (
        "L, recall why we created Project L, compare the original architecture "
        "with what you can do now and identify contradictions."
    )
    assert rhee.exhaustive_requested(prompt) is False
    assert rhee.evidence_mode_requested(prompt) is False
    terms = rhee.database_search_terms(prompt)
    assert {"rike", "rhee", "mary", "quinn", "carol", "sara"}.issubset(set(terms))
    assert "project" not in terms
    assert len(terms) <= 24


def test_deep_recall_is_explicit_without_hijacking_full_swot():
    assert rhee.deep_recall_requested("Deep recall Leah") is True
    assert rhee.exhaustive_requested("Deep recall Leah") is True
    assert rhee.evidence_mode_requested("Deep recall Leah") is True
    assert rhee.exhaustive_requested("Can you do a full SWOT analysis on yourself") is False
    assert rhee.exhaustive_requested("Tell me all about Leah") is False
    assert "deep" not in rhee.database_search_terms("Deep recall Leah")
    assert "leah" in rhee.database_search_terms("Deep recall Leah")


def test_month_first_dates_are_detected_and_prioritised_for_breakup_recall():
    query = "When did I break up with Leah"
    exact = {
        "content": "Doug and Leah's relationship ended on July 27, 2025.",
        "primary_subject": "Leah",
        "importance": 0,
        "salience": 0,
    }
    generic = {
        "content": "Doug reflected on his relationship with Leah.",
        "primary_subject": "Leah",
        "importance": 100,
        "salience": 100,
    }

    assert rhee.contains_explicit_date("July 27, 2025") is True
    assert rhee.contains_explicit_date("27 July 2025") is True
    assert rhee.calculate_memory_score(exact, query) > rhee.calculate_memory_score(generic, query)
    assert rhee.calculate_raw_score({**exact, "role": "user"}, query) > 0


def test_historical_question_without_question_mark_is_not_evidence():
    query = "When did I break up with Leah"
    assert rhee.calculate_raw_score({"content": query, "role": "user"}, query) == 0


def test_indexed_search_failure_preserves_full_scan_fallback(monkeypatch):
    class BrokenQuery:
        def execute(self):
            raise RuntimeError("RPC unavailable")

    class BrokenClient:
        def rpc(self, name, params):
            return BrokenQuery()

    monkeypatch.setattr(rhee, "supabase", BrokenClient())
    assert rhee.search_database_candidates("Luella") is None


def test_indexed_search_retries_with_safe_bounds_before_full_scan(monkeypatch):
    calls = []

    class RetryQuery:
        def __init__(self, params):
            self.params = params

        def execute(self):
            if len(calls) == 1:
                raise RuntimeError("statement timeout")
            return type("Response", (), {"data": {"raw": [], "memories": []}})()

    class RetryClient:
        def rpc(self, name, params):
            calls.append((name, params))
            return RetryQuery(params)

    monkeypatch.setattr(rhee, "supabase", RetryClient())
    result = rhee.search_database_candidates("Deep recall Leah", raw_limit=200, memory_limit=120)

    assert result == {"raw": [], "memories": []}
    assert len(calls) == 2
    assert calls[1][1]["p_raw_limit"] == 100
    assert calls[1][1]["p_memory_limit"] == 60


def test_candidate_recall_keeps_local_library_and_database_provenance(monkeypatch):
    monkeypatch.setattr(
        rhee,
        "load_local_memories",
        lambda: [{"content": "Luella enjoys netball.", "role": "user", "_table": "local_family"}],
    )
    database_rows = [{
        "content": "Luella got her braces off.",
        "_table": "memory_family",
        "_source_role": "user",
        "_provenance_evidence": "raw_catchall",
    }]

    packet = rhee.build_recall_packet(
        "Tell me about Luella and her braces",
        limit=10,
        database_memories=database_rows,
    )

    assert any(row["_table"] == "memory_family" for row in packet)
    assert any(row["_table"] == "local_family" for row in packet)
    assert all(row["_source_role"] == "user" for row in packet)


def test_pauline_six_month_report_is_a_real_deep_recall_mode():
    prompt = "Can you write a full report for Pauline based on my last 6 months"
    assert rhee.pauline_report_requested(prompt) is True
    assert rhee.deep_recall_requested(prompt) is True
    assert rhee.exhaustive_requested(prompt) is True
    terms = set(rhee.database_search_terms(prompt))
    assert {"pauline", "recovery", "therapy", "meeting", "trauma"} <= terms
    assert rhee.pauline_report_requested("Write a software report") is False


def test_pauline_report_memory_selection_balances_domains(monkeypatch):
    monkeypatch.setattr(rhee, "load_local_memories", lambda: [])
    rows = [
        {
            "id": index,
            "content": f"Recovery meeting and sponsor progress record {index}",
            "_table": "memory_recovery",
            "_source_role": "user",
        }
        for index in range(12)
    ]
    rows.extend([
        {
            "id": 100 + index,
            "content": f"Health and therapy progress record {index}",
            "_table": "memory_health",
            "_source_role": "user",
        }
        for index in range(3)
    ])

    packet = rhee.build_recall_packet(
        "Full report for Pauline based on my last six months",
        limit=10,
        database_memories=rows,
    )

    tables = [row["_table"] for row in packet]
    assert tables.count("memory_recovery") == 8
    assert tables.count("memory_health") == 2


def test_pauline_report_ranking_prefers_dated_session_reports():
    generic = {
        "id": 1,
        "_table": "memory_family",
        "content": "Family recovery therapy progress and relationships.",
        "importance": 9,
        "salience": 9,
    }
    dated_report = {
        "id": 2,
        "_table": "memory_relationships",
        "content": "Pauline Session Report — 25 August 2026. Recovery and trauma insight.",
        "importance": 1,
        "salience": 1,
    }

    query = "Can you write a full report for Pauline based on my last 6 months"
    assert rhee.calculate_memory_score(dated_report, query) > rhee.calculate_memory_score(generic, query)


def test_pauline_report_packet_preserves_long_evidence_excerpt():
    marker = "DETAIL_AFTER_700"
    memory = {
        "id": 22,
        "_table": "memory_recovery",
        "content": "Pauline report 25 August 2026 " + ("x" * 720) + marker,
        "_score": 100,
    }

    formatted = rhee.format_memory_packet(
        "full report for Pauline based on my last six months",
        [memory],
    )

    assert marker in formatted
