from types import SimpleNamespace

from layers.layer11_true_deep_recall import install


class FakeQuery:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error

    def select(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def range(self, *args, **kwargs):
        return self

    def execute(self):
        if self.error:
            raise self.error
        return SimpleNamespace(data=[dict(row) for row in self.rows])


class FakeSupabase:
    def __init__(self, raw_rows=None, error=None):
        self.raw_rows = raw_rows or []
        self.error = error

    def table(self, name):
        assert name == "raw_catchall"
        return FakeQuery(self.raw_rows, self.error)


def fake_rhee(*, supabase=None):
    state = {"circuit": False}

    def previous_search(query, raw_limit=200, memory_limit=80, receipt_out=None):
        if receipt_out is not None:
            receipt_out["previous_search_called"] = True
        return {"raw": [], "memories": []}

    rhee = SimpleNamespace(
        plan_recall=lambda query, today=None: {"mode": "focused"},
        search_database_candidates=previous_search,
        safe_text=lambda value: "" if value is None else str(value).strip(),
        term_in_text=lambda needle, text: needle in text,
        time=SimpleNamespace(monotonic=lambda: 10.0),
        recall_query_key=lambda terms: "query-key",
        database_search_terms=lambda query: ["leah"],
        supabase=supabase,
        recall_rpc_retry_after=lambda: 8 if state["circuit"] else 0,
        open_recall_rpc_circuit=lambda: state.update(circuit=True),
        close_recall_rpc_circuit=lambda: state.update(circuit=False),
        recall_rpc_error_code=lambda exc: str(getattr(exc, "code", "") or ""),
        LONG_TERM_TABLES=["memory_general"],
        load_local_memories=lambda: [{"id": "local", "content": "local"}],
        load_table_memories=lambda table: [{"id": "live", "content": "live"}],
        build_raw_role_index=lambda rows: {},
        annotate_memory_provenance=lambda memory, index: memory,
        deduplicate_memories=lambda rows: rows,
    )
    rhee._test_state = state
    return rhee


def test_layer11_preserves_receipt_argument_for_ordinary_recall():
    rhee = fake_rhee()
    install(rhee)
    receipt = {}

    result = rhee.search_database_candidates(
        "ordinary recall",
        receipt_out=receipt,
    )

    assert result == {"raw": [], "memories": []}
    assert receipt["previous_search_called"] is True


def test_layer11_fails_closed_when_live_full_corpus_probe_fails():
    class SchemaCacheUnavailable(Exception):
        code = "PGRST002"

    rhee = fake_rhee(
        supabase=FakeSupabase(error=SchemaCacheUnavailable("schema cache unavailable"))
    )
    install(rhee)
    receipt = {}

    result = rhee.search_database_candidates(
        "deep recall Leah",
        receipt_out=receipt,
    )

    assert result is None
    assert rhee._test_state["circuit"] is True
    assert receipt["retrieval_status"] == "unavailable"
    assert receipt["retrieval_reason"] == "full_corpus_incomplete"
    assert receipt["retrieval_error_code"] == "PGRST002"
    assert receipt["retrieval_query_binding"] == "full-corpus-unverified"


def test_layer11_marks_only_complete_live_scan_as_full_corpus():
    rhee = fake_rhee(
        supabase=FakeSupabase(
            raw_rows=[{"id": 1, "role": "user", "content": "direct evidence"}]
        )
    )
    install(rhee)
    receipt = {}

    result = rhee.search_database_candidates(
        "deep recall Leah",
        receipt_out=receipt,
    )

    assert result["raw"] == [
        {"id": 1, "role": "user", "content": "direct evidence"}
    ]
    assert {row["id"] for row in result["memories"]} == {"local", "live"}
    assert receipt["retrieval_status"] == "checked"
    assert receipt["retrieval_query_binding"] == "full-corpus-live"
    assert receipt["full_scan_raw_rows"] == 1
    assert receipt["full_scan_memory_rows"] == 2
    assert rhee._test_state["circuit"] is False
