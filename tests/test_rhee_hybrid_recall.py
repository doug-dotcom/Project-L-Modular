import pytest

import agents.rhee.rhee_v3 as rhee
from memory.retrieval.cache_state import (
    cache_generation,
    invalidate_recall_caches,
)


TEST_OWNER_ID = "00000000-0000-4000-8000-000000000001"


@pytest.fixture(autouse=True)
def _configured_project_l_memory_owner(monkeypatch):
    monkeypatch.setenv("L_MEMORY_OWNER_ID", TEST_OWNER_ID)
    monkeypatch.delenv("PROJECT_L_OWNER_ID", raising=False)


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
    receipt = {}
    rhee._recall_rpc_circuit_open_until = 0.0

    class RpcQuery:
        def __init__(self, params):
            self.params = params

        def execute(self):
            return type("Response", (), {"data": {
                "status": "ok",
                "matches": [{
                    "id": "8",
                    "domain": "family",
                    "subject": "Luella",
                    "content": "Luella got her braces off.",
                    "importance": 80,
                    "salience": 90,
                    "anchor": False,
                    "createdAt": "2026-06-16T00:00:00+00:00",
                    "matchScore": 44.2,
                    "provenance": {
                        "sourceTable": "memory_family",
                        "sourceId": "8",
                        "rawId": 7,
                        "sourceRole": "user",
                    },
                }],
                "returnedCount": 1,
                "scope": {"ownerBound": True, "allowedDomainCount": 9},
                "queryKey": self.params["p_query_key"],
                "queryContractVersion": "2",
            }})()

    class RpcClient:
        def rpc(self, name, params):
            calls.append((name, params))
            return RpcQuery(params)

    monkeypatch.setattr(rhee, "supabase", RpcClient())
    result = rhee.search_database_candidates(
        "When did Luella get her braces off?",
        receipt_out=receipt,
    )

    assert len(calls) == 1
    assert calls[0][0] == "project_l_memory_context_service_v2"
    assert calls[0][1]["p_user"] == TEST_OWNER_ID
    assert calls[0][1]["p_limit"] == 6
    assert calls[0][1]["p_char_budget"] <= 12000
    assert {"luella", "braces"}.issubset(set(calls[0][1]["p_terms"]))
    assert calls[0][1]["p_query_key"] == rhee.recall_query_key(calls[0][1]["p_terms"])
    assert receipt["retrieval_query_binding"] == "server-verified"
    assert receipt["retrieval_owner_bound"] is True
    assert receipt["retrieval_scope"] == "owner-scoped-v2"
    assert result["raw"] == []
    assert result["memories"][0]["raw_id"] == 7
    assert result["memories"][0]["_table"] == "memory_family"
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
    assert rhee.explicit_deep_recall_requested("Deep recall Leah") is True
    assert rhee.deep_recall_requested("Deep recall Leah") is True
    assert rhee.exhaustive_requested("Deep recall Leah") is True
    assert rhee.evidence_mode_requested("Deep recall Leah") is True
    assert rhee.exhaustive_requested("Can you do a full SWOT analysis on yourself") is False
    assert rhee.exhaustive_requested("Tell me all about Leah") is False
    assert "deep" not in rhee.database_search_terms("Deep recall Leah")
    assert "leah" in rhee.database_search_terms("Deep recall Leah")


def test_semantic_broad_recall_does_not_report_explicit_deep_recall():
    from types import SimpleNamespace
    from layers.layer6_semantic_query_rewriter import install

    prompt = "Recall diving Bali"
    fake = SimpleNamespace(
        expanded_query_terms=lambda query: [],
        deep_recall_requested=rhee.explicit_deep_recall_requested,
        plan_recall=lambda query, today=None: {
            "mode": "focused",
            "raw_candidates": 20,
            "memory_candidates": 20,
            "evidence_char_budget": 8000,
            "retrieval_budget_ms": 1000,
        },
        safe_text=rhee.safe_text,
    )
    install(fake)

    assert fake.deep_recall_requested(prompt) is True
    assert rhee.explicit_deep_recall_requested(prompt) is False



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


def test_owner_scoped_search_fails_closed_without_owner_binding(monkeypatch):
    receipt = {}

    class Client:
        def rpc(self, name, params):
            raise AssertionError("RPC must not run without an owner binding")

    monkeypatch.delenv("L_MEMORY_OWNER_ID", raising=False)
    monkeypatch.delenv("PROJECT_L_OWNER_ID", raising=False)
    monkeypatch.setattr(rhee, "supabase", Client())

    result = rhee.search_database_candidates("Recall diving Bali", receipt_out=receipt)

    assert result is None
    assert receipt["retrieval_status"] == "unavailable"
    assert receipt["retrieval_reason"] == "owner_binding_not_configured"
    assert receipt["retrieval_owner_bound"] is False


def test_owner_scoped_candidate_adapter_preserves_provenance():
    candidate = rhee.owner_scoped_memory_candidate({
        "id": "5508",
        "subject": "Doug",
        "content": "Tulamben, Bali diving memory.",
        "importance": 90,
        "salience": 80,
        "anchor": True,
        "createdAt": "2026-09-13T13:16:40+00:00",
        "matchScore": 51.7,
        "provenance": {
            "sourceTable": "memory_sport",
            "sourceId": "5508",
            "rawId": 5689,
            "sourceRole": "user",
        },
    })

    assert candidate["_table"] == "memory_sport"
    assert candidate["raw_id"] == 5689
    assert candidate["_source_role"] == "user"
    assert candidate["_provenance_evidence"] == "owner_scoped_v2"
    assert candidate["content"] == "Tulamben, Bali diving memory."


def test_indexed_search_failure_preserves_full_scan_fallback(monkeypatch):
    calls = []
    receipt = {}
    rhee._recall_rpc_circuit_open_until = 0.0

    class BrokenQuery:
        def execute(self):
            raise RuntimeError("RPC unavailable")

    class BrokenClient:
        def rpc(self, name, params):
            calls.append((name, params))
            return BrokenQuery()

    monkeypatch.setattr(rhee, "supabase", BrokenClient())
    assert rhee.search_database_candidates("Luella", receipt_out=receipt) is None
    assert len(calls) == 1
    assert receipt["retrieval_error_code"] == "non_transient"


def test_indexed_search_retries_with_safe_bounds_before_full_scan(monkeypatch):
    calls = []
    sleeps = []
    receipt = {}
    rhee._recall_rpc_circuit_open_until = 0.0

    class StatementTimeout(Exception):
        code = "57014"
        message = "canceling statement due to statement timeout"

    class RetryQuery:
        def __init__(self, params):
            self.params = params

        def execute(self):
            if len(calls) == 1:
                raise StatementTimeout()
            return type("Response", (), {"data": {
                "status": "ok",
                "matches": [],
                "returnedCount": 0,
                "scope": {"ownerBound": True, "allowedDomainCount": 9},
                "queryKey": self.params["p_query_key"],
                "queryContractVersion": "2",
            }})()

    class RetryClient:
        def rpc(self, name, params):
            calls.append((name, params))
            return RetryQuery(params)

    monkeypatch.setattr(rhee, "supabase", RetryClient())
    monkeypatch.setattr(rhee.time, "sleep", lambda delay: sleeps.append(delay))
    result = rhee.search_database_candidates(
        "Deep recall Leah",
        raw_limit=200,
        memory_limit=120,
        receipt_out=receipt,
    )

    assert result == {"raw": [], "memories": []}
    assert len(calls) == 2
    assert calls[0][1]["p_query_key"] == calls[1][1]["p_query_key"]
    assert calls[1][1]["p_limit"] == 4
    assert calls[1][1]["p_char_budget"] == 7200
    assert sleeps == [0.2]
    assert receipt["retrieval_attempts"] == 2
    assert receipt["retrieval_query_binding"] == "server-verified"


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



def test_indexed_search_fails_closed_when_v2_function_is_missing(monkeypatch):
    calls = []
    receipt = {}
    rhee._recall_rpc_circuit_open_until = 0.0

    class MissingFunction(Exception):
        code = "PGRST202"
        message = "Could not find the function public.project_l_memory_context_service_v2"

    class MissingQuery:
        def execute(self):
            raise MissingFunction()

    class Client:
        def rpc(self, name, params):
            calls.append(name)
            return MissingQuery()

    monkeypatch.setattr(rhee, "supabase", Client())
    result = rhee.search_database_candidates("Luella braces", receipt_out=receipt)

    assert result is None
    assert calls == ["project_l_memory_context_service_v2"]
    assert receipt["retrieval_status"] == "unavailable"
    assert receipt["retrieval_query_binding"] == "server-verified"


def test_indexed_search_rejects_wrong_query_cohort(monkeypatch):
    calls = []
    receipt = {}
    rhee._recall_rpc_circuit_open_until = 0.0

    class Query:
        def execute(self):
            return type("Response", (), {
                "data": {
                    "status": "ok",
                    "matches": [],
                    "returnedCount": 0,
                    "scope": {"ownerBound": True, "allowedDomainCount": 9},
                    "queryKey": "wrong",
                    "queryContractVersion": "2",
                }
            })()

    class Client:
        def rpc(self, name, params):
            calls.append(name)
            return Query()

    monkeypatch.setattr(rhee, "supabase", Client())
    result = rhee.search_database_candidates("Luella braces", receipt_out=receipt)

    assert result is None
    assert calls == ["project_l_memory_context_service_v2"]
    assert receipt["retrieval_error_code"] == "non_transient"


def test_evidence_independence_counts_lineages_not_representations():
    receipt = rhee.evidence_independence_receipt([
        {"source": "raw_catchall:44", "raw_id": None},
        {"source": "memory_family:7", "raw_id": 44},
        {"source": "memory_health:8", "raw_id": 44},
        {"source": "raw_catchall:99", "raw_id": None},
    ])

    assert receipt["evidence_items"] == 4
    assert receipt["independent_lineages"] == 2
    assert receipt["shared_lineages"] == 1
    assert receipt["duplicate_representations"] == 2
    assert receipt["confidence_counts_lineages_not_copies"] is True

    assert receipt["governed_evidence_items"] == 0
    assert receipt["owner_bound_governed_items"] == 0
    assert receipt["governance_metadata_complete"] is False
    assert receipt["authority_classes"] == {}
    assert receipt["freshness_classes"] == {}


def test_evidence_independence_reports_governed_authority_and_freshness():
    receipt = rhee.evidence_independence_receipt([
        {
            "source": "memory_sport:7",
            "raw_id": 44,
            "provenance": "owner_scoped_v2",
            "owner_bound": True,
            "authority": {"class": "direct_user_promoted_memory", "precedence": 70},
            "freshness": {"class": "non_temporal_memory"},
        },
        {
            "source": "memory_general:8",
            "raw_id": 99,
            "provenance": "owner_scoped_v2",
            "owner_bound": True,
            "authority": {"class": "assistant_derived_promoted_memory", "precedence": 45},
            "freshness": {"class": "non_temporal_memory"},
        },
    ])

    assert receipt["governed_evidence_items"] == 2
    assert receipt["owner_bound_governed_items"] == 2
    assert receipt["governance_metadata_complete"] is True
    assert receipt["authority_classes"] == {
        "direct_user_promoted_memory": 1,
        "assistant_derived_promoted_memory": 1,
    }
    assert receipt["freshness_classes"] == {"non_temporal_memory": 2}


def test_evidence_independence_marks_incomplete_governance_metadata():
    receipt = rhee.evidence_independence_receipt([
        {
            "source": "memory_sport:7",
            "raw_id": 44,
            "provenance": "owner_scoped_v2",
            "owner_bound": False,
            "authority": None,
            "freshness": {"class": "non_temporal_memory"},
        },
    ])

    assert receipt["governed_evidence_items"] == 1
    assert receipt["owner_bound_governed_items"] == 0
    assert receipt["governance_metadata_complete"] is False
    assert receipt["authority_classes"] == {"unknown": 1}



def test_indexed_search_rejects_wrong_query_contract_version(monkeypatch):
    receipt = {}
    rhee._recall_rpc_circuit_open_until = 0.0

    class Query:
        def __init__(self, params):
            self.params = params

        def execute(self):
            return type("Response", (), {
                "data": {
                    "status": "ok",
                    "matches": [],
                    "returnedCount": 0,
                    "scope": {"ownerBound": True, "allowedDomainCount": 9},
                    "queryKey": self.params["p_query_key"],
                    "queryContractVersion": "1",
                }
            })()

    class Client:
        def rpc(self, name, params):
            assert name == "project_l_memory_context_service_v2"
            return Query(params)

    monkeypatch.setattr(rhee, "supabase", Client())
    result = rhee.search_database_candidates(
        "Luella braces",
        receipt_out=receipt,
    )

    assert result is None
    assert receipt["retrieval_status"] == "unavailable"
    assert receipt["retrieval_error_code"] == "non_transient"



def test_sparse_recall_escalation_never_promotes_itself_to_explicit_deep_recall():
    from types import SimpleNamespace
    from layers.layer7_retrieval_escalation import install

    from contextvars import ContextVar

    calls = []
    origin_guard = ContextVar("test_internal_recall_pass", default=False)

    def base_packet(query):
        calls.append((query, origin_guard.get()))
        return {
            "evidence": [],
            "context": "",
            "context_size": 0,
            "recall_active": False,
            "recall_plan": {"status": "checked"},
        }

    fake = SimpleNamespace(
        build_context_packet=base_packet,
        safe_text=lambda value: "" if value is None else str(value).strip(),
        _project_l_internal_recall_pass=origin_guard,
    )

    install(fake)
    result = fake.build_context_packet("Recall diving Bali")

    assert result["recall_plan"]["retrieval_escalation"] == "performed"
    assert len(calls) == 2
    assert calls[0] == ("Recall diving Bali", False)
    assert calls[1][1] is True
    assert "deep recall" not in calls[1][0].lower()
    assert "comprehensive recall history" in calls[1][0].lower()
    assert origin_guard.get() is False


def test_internal_recall_origin_blocks_true_deep_recall_promotion():
    from contextvars import ContextVar
    from types import SimpleNamespace
    from layers.layer11_true_deep_recall import install

    origin_guard = ContextVar("test_true_deep_recall_origin", default=False)

    def base_plan(query, today=None):
        return {"mode": "focused", "retrieval_budget_ms": 1000}

    def base_search(query, raw_limit=200, memory_limit=80, receipt_out=None):
        return {"raw": [], "memories": []}

    fake = SimpleNamespace(
        plan_recall=base_plan,
        search_database_candidates=base_search,
        safe_text=lambda value: "" if value is None else str(value).strip(),
        term_in_text=lambda term, text: term in text,
        _project_l_internal_recall_pass=origin_guard,
    )
    install(fake)

    token = origin_guard.set(True)
    try:
        internal = fake.plan_recall("deep recall family history")
    finally:
        origin_guard.reset(token)

    user_entry = fake.plan_recall("deep recall family history")

    assert internal["mode"] == "focused"
    assert "deep_recall_contract" not in internal
    assert user_entry["mode"] == "investigate"
    assert user_entry["deep_recall_contract"] == "full_corpus_scan"


def test_recall_origin_guard_is_request_local_and_idempotent():
    from types import SimpleNamespace
    from layers.layer67_recall_origin_guard import install

    fake = SimpleNamespace()
    install(fake)
    first = fake._project_l_internal_recall_pass
    install(fake)

    assert fake._project_l_internal_recall_pass is first
    assert first.get() is False


def test_owner_scoped_evidence_preserves_governance_metadata():
    memory = {
        "id": "42",
        "_table": "memory_sport",
        "raw_id": 5685,
        "content": "Doug completed his Bali diving qualifications.",
        "created_at": "2026-09-13T13:09:09Z",
        "_source_role": "user",
        "_provenance_evidence": "owner_scoped_v2",
        "_owner_scoped_authority": {
            "class": "direct_user_promoted_memory",
            "precedence": 70,
        },
        "_owner_scoped_freshness": {
            "class": "non_temporal_memory",
            "temporalCurrentnessHandledSeparately": True,
        },
    }
    evidence = []

    rhee.format_memory_packet("Recall diving Bali", [memory], evidence_out=evidence)

    assert len(evidence) == 1
    item = evidence[0]
    assert item["source"] == "memory_sport:42"
    assert item["raw_id"] == 5685
    assert item["provenance"] == "owner_scoped_v2"
    assert item["owner_bound"] is True
    assert item["authority"]["class"] == "direct_user_promoted_memory"
    assert item["authority"]["precedence"] == 70
    assert item["freshness"]["class"] == "non_temporal_memory"


def test_unlinked_evidence_does_not_claim_owner_binding():
    memory = {
        "id": "local-1",
        "_table": "local_family",
        "content": "Local compatibility memory.",
        "_source_role": "user",
    }
    evidence = []

    rhee.format_memory_packet("Recall family", [memory], evidence_out=evidence)

    assert len(evidence) == 1
    assert evidence[0]["provenance"] == "unlinked"
    assert evidence[0]["owner_bound"] is False
    assert evidence[0]["authority"] is None



def test_recall_confidence_uses_governed_independent_lineages():
    from types import SimpleNamespace
    from layers.layer10_recall_confidence import install

    evidence = [{"source": f"memory_general:{i}", "raw_id": i} for i in range(12)]
    base = {
        "context": "base",
        "evidence": evidence,
        "recall_plan": {"status": "checked"},
        "evidence_independence": {
            "independent_lineages": 6,
            "governed_evidence_items": 12,
            "governance_metadata_complete": True,
        },
    }
    fake = SimpleNamespace(
        build_context_packet=lambda query: dict(base),
        safe_text=lambda value: "" if value is None else str(value),
    )
    install(fake)

    result = fake.build_context_packet("Recall diving")
    confidence = result["recall_confidence"]

    assert confidence["state"] == "supported_retrieval"
    assert confidence["confidence"] == "high"
    assert confidence["independent_lineages"] == 6
    assert confidence["governed_evidence_sources"] == 12
    assert confidence["governance_metadata_complete"] is True


def test_recall_confidence_does_not_overstate_duplicated_or_ungoverned_support():
    from types import SimpleNamespace
    from layers.layer10_recall_confidence import install

    evidence = [{"source": f"memory_general:{i}", "raw_id": 44} for i in range(12)]
    base = {
        "context": "base",
        "evidence": evidence,
        "recall_plan": {"status": "checked"},
        "evidence_independence": {
            "independent_lineages": 1,
            "governed_evidence_items": 12,
            "governance_metadata_complete": False,
        },
    }
    fake = SimpleNamespace(
        build_context_packet=lambda query: dict(base),
        safe_text=lambda value: "" if value is None else str(value),
    )
    install(fake)

    result = fake.build_context_packet("Recall diving")
    confidence = result["recall_confidence"]

    assert confidence["state"] == "supported_retrieval"
    assert confidence["confidence"] == "moderate"
    assert confidence["independent_lineages"] == 1
    assert confidence["governance_metadata_complete"] is False



def test_authority_review_prefers_governed_precedence_over_legacy_role():
    from types import SimpleNamespace
    from layers.layer9_authority_conflict import install

    evidence = [
        {
            "source": "memory_general:legacy-user",
            "role": "user",
            "quote_source": "legacy role-only evidence",
        },
        {
            "source": "memory_general:governed",
            "role": "assistant",
            "quote_source": "governed direct-user promoted evidence",
            "provenance": "owner_scoped_v2",
            "authority": {
                "class": "direct_user_promoted_memory",
                "precedence": 70,
            },
        },
    ]
    fake = SimpleNamespace(
        build_context_packet=lambda query: {
            "context": "base",
            "evidence": list(evidence),
            "recall_plan": {"status": "checked"},
        },
        safe_text=lambda value: "" if value is None else str(value).strip(),
    )
    install(fake)

    result = fake.build_context_packet("Recall")
    ordered = result["evidence"]

    assert ordered[0]["source"] == "memory_general:governed"
    assert result["recall_plan"]["authority_contract"] == "owner-scoped-v2-precedence-first"
    assert result["recall_plan"]["authority_counts"]["user_primary"] == 2


def test_authority_review_orders_governed_items_by_precedence():
    from types import SimpleNamespace
    from layers.layer9_authority_conflict import install

    evidence = [
        {
            "source": "memory_general:derived",
            "provenance": "owner_scoped_v2",
            "authority": {"class": "assistant_derived_promoted_memory", "precedence": 45},
        },
        {
            "source": "memory_general:direct",
            "provenance": "owner_scoped_v2",
            "authority": {"class": "direct_user_promoted_memory", "precedence": 70},
        },
    ]
    fake = SimpleNamespace(
        build_context_packet=lambda query: {
            "context": "base",
            "evidence": list(evidence),
            "recall_plan": {"status": "checked"},
        },
        safe_text=lambda value: "" if value is None else str(value).strip(),
    )
    install(fake)

    result = fake.build_context_packet("Recall")

    assert [item["source"] for item in result["evidence"]] == [
        "memory_general:direct",
        "memory_general:derived",
    ]



def test_recall_confidence_downgrades_unresolved_same_fact_conflict():
    from types import SimpleNamespace
    from layers.layer10_recall_confidence import install

    evidence = [{"source": f"memory_general:{i}", "raw_id": i} for i in range(12)]
    base = {
        "context": "base",
        "evidence": evidence,
        "recall_plan": {
            "status": "checked",
            "authority_review": "applied",
            "conflict_policy": "preserve_primary_conflicts_and_prefer_explicit_user_corrections",
            "unresolved_conflict": True,
        },
        "evidence_independence": {
            "independent_lineages": 8,
            "governed_evidence_items": 12,
            "governance_metadata_complete": True,
        },
    }
    fake = SimpleNamespace(
        build_context_packet=lambda query: dict(base),
        safe_text=lambda value: "" if value is None else str(value),
    )
    install(fake)

    result = fake.build_context_packet("Recall")
    confidence = result["recall_confidence"]

    assert confidence["state"] == "conflicted_retrieval"
    assert confidence["confidence"] == "moderate"
    assert confidence["unresolved_conflict"] is True
    assert result["recall_plan"]["recall_conflict_state"] == "unresolved"


def test_recall_confidence_preserves_high_support_when_no_conflict_reported():
    from types import SimpleNamespace
    from layers.layer10_recall_confidence import install

    evidence = [{"source": f"memory_general:{i}", "raw_id": i} for i in range(12)]
    base = {
        "context": "base",
        "evidence": evidence,
        "recall_plan": {
            "status": "checked",
            "authority_review": "applied",
            "conflict_policy": "preserve_primary_conflicts_and_prefer_explicit_user_corrections",
        },
        "evidence_independence": {
            "independent_lineages": 8,
            "governed_evidence_items": 12,
            "governance_metadata_complete": True,
        },
    }
    fake = SimpleNamespace(
        build_context_packet=lambda query: dict(base),
        safe_text=lambda value: "" if value is None else str(value),
    )
    install(fake)

    result = fake.build_context_packet("Recall")
    confidence = result["recall_confidence"]

    assert confidence["state"] == "supported_retrieval"
    assert confidence["confidence"] == "high"
    assert confidence["unresolved_conflict"] is False



def test_authority_review_establishes_fail_closed_conflict_state_contract():
    from types import SimpleNamespace
    from layers.layer9_authority_conflict import install

    fake = SimpleNamespace(
        build_context_packet=lambda query: {
            "context": "base",
            "evidence": [{"source": "memory_general:1", "role": "user"}],
            "recall_plan": {"status": "checked"},
        },
        safe_text=lambda value: "" if value is None else str(value).strip(),
    )
    install(fake)

    result = fake.build_context_packet("Recall")

    assert result["recall_plan"]["conflict_state"] == "none_reported"
    assert result["recall_plan"]["unresolved_conflict"] is False


def test_authority_review_preserves_explicit_upstream_unresolved_conflict():
    from types import SimpleNamespace
    from layers.layer9_authority_conflict import install

    fake = SimpleNamespace(
        build_context_packet=lambda query: {
            "context": "base",
            "evidence": [{"source": "memory_general:1", "role": "user"}],
            "recall_plan": {"status": "checked", "conflict_state": "unresolved"},
        },
        safe_text=lambda value: "" if value is None else str(value).strip(),
    )
    install(fake)

    result = fake.build_context_packet("Recall")

    assert result["recall_plan"]["conflict_state"] == "unresolved"
    assert result["recall_plan"]["unresolved_conflict"] is True


def test_authority_review_rejects_unknown_conflict_state():
    from types import SimpleNamespace
    from layers.layer9_authority_conflict import install

    fake = SimpleNamespace(
        build_context_packet=lambda query: {
            "context": "base",
            "evidence": [{"source": "memory_general:1", "role": "user"}],
            "recall_plan": {"status": "checked", "conflict_state": "keyword_guess"},
        },
        safe_text=lambda value: "" if value is None else str(value).strip(),
    )
    install(fake)

    result = fake.build_context_packet("Recall")

    assert result["recall_plan"]["conflict_state"] == "none_reported"
    assert result["recall_plan"]["unresolved_conflict"] is False



def test_final_deep_recall_conflict_reconciliation_preserves_reviewed_unresolved_state():
    from types import SimpleNamespace
    from layers.layer40_deep_recall_final_conflict_reconciliation import install

    fake = SimpleNamespace(
        build_context_packet=lambda query: {
            "context": "base",
            "evidence": [{"source": "memory_general:1", "quote_source": "fact"}],
            "recall_plan": {"status": "checked", "conflict_state": "unresolved"},
        },
        safe_text=lambda value: "" if value is None else str(value).strip(),
        term_in_text=lambda term, text: term in text,
        load_all_raw_catchall=lambda: [],
        load_all_memories=lambda: [],
    )
    install(fake)

    result = fake.build_context_packet("deep recall history")

    assert result["recall_plan"]["conflict_state"] == "unresolved"
    assert result["recall_plan"]["unresolved_conflict"] is True
    assert result["recall_plan"]["deep_recall_conflict_state_handoff"] == "reviewed-state-only"


def test_final_deep_recall_conflict_reconciliation_does_not_infer_from_cue_words():
    from types import SimpleNamespace
    from layers.layer40_deep_recall_final_conflict_reconciliation import install

    fake = SimpleNamespace(
        build_context_packet=lambda query: {
            "context": "base",
            "evidence": [{
                "source": "memory_general:1",
                "quote_source": "Actually this was updated later.",
                "role": "user",
            }],
            "recall_plan": {"status": "checked", "conflict_state": "none_reported"},
        },
        safe_text=lambda value: "" if value is None else str(value).strip(),
        term_in_text=lambda term, text: term in text,
        load_all_raw_catchall=lambda: [],
        load_all_memories=lambda: [],
    )
    install(fake)

    result = fake.build_context_packet("deep recall history")

    assert result["recall_plan"]["deep_recall_final_conflict_cue_sources"] == ["memory_general:1"]
    assert result["recall_plan"]["conflict_state"] == "none_reported"
    assert result["recall_plan"]["unresolved_conflict"] is False



def test_reviewed_conflict_state_requires_explicit_reviewer_and_allowed_state():
    from types import SimpleNamespace
    from layers.layer9_authority_conflict import install

    fake = SimpleNamespace(
        build_context_packet=lambda query: {
            "context": "base",
            "evidence": [{"source": "memory_general:1", "role": "user"}],
            "recall_plan": {"status": "checked"},
        },
        safe_text=lambda value: "" if value is None else str(value).strip(),
    )
    install(fake)

    plan = {"status": "checked"}
    fake.set_reviewed_conflict_state(
        plan,
        "temporal_transition",
        reviewer="layer60_event_identity",
        basis="different reviewed event stages",
    )

    assert plan["conflict_state"] == "temporal_transition"
    assert plan["unresolved_conflict"] is False
    assert plan["conflict_state_reviewed"] is True
    assert plan["conflict_state_reviewer"] == "layer60_event_identity"

    try:
        fake.set_reviewed_conflict_state(plan, "keyword_guess", reviewer="test")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_authority_review_does_not_trust_unreviewed_conflict_state():
    from types import SimpleNamespace
    from layers.layer9_authority_conflict import install

    fake = SimpleNamespace(
        build_context_packet=lambda query: {
            "context": "base",
            "evidence": [{"source": "memory_general:1", "role": "user"}],
            "recall_plan": {
                "status": "checked",
                "conflict_state": "unresolved",
                "conflict_state_reviewed": False,
            },
        },
        safe_text=lambda value: "" if value is None else str(value).strip(),
    )
    install(fake)

    result = fake.build_context_packet("Recall")

    assert result["recall_plan"]["conflict_state"] == "none_reported"
    assert result["recall_plan"]["unresolved_conflict"] is False
