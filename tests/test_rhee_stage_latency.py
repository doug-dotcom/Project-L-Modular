import agents.rhee.rhee_v3 as rhee


class StepClock:
    def __init__(self, step=0.01):
        self.value = 0.0
        self.step = step

    def __call__(self):
        self.value += self.step
        return self.value


def plan():
    return {
        "mode": "focused",
        "raw_candidates": 12,
        "memory_candidates": 6,
        "retrieval_budget_ms": 5000,
        "period": None,
    }


def install_fast_context_dependencies(monkeypatch):
    monkeypatch.setattr(rhee, "load_identity", lambda: "identity")
    monkeypatch.setattr(
        rhee,
        "load_learnings",
        lambda user_message="": "learnings",
    )
    monkeypatch.setattr(rhee, "exhaustive_requested", lambda query: False)
    monkeypatch.setattr(rhee, "deep_recall_requested", lambda query: False)
    monkeypatch.setattr(
        rhee,
        "explicit_deep_recall_requested",
        lambda query: False,
    )
    monkeypatch.setattr(rhee, "pauline_report_requested", lambda query: False)
    monkeypatch.setattr(
        rhee,
        "search_database_candidates",
        lambda *args, **kwargs: {"raw": [], "memories": []},
    )
    monkeypatch.setattr(
        rhee,
        "build_raw_recall_packet",
        lambda *args, **kwargs: "continuity",
    )
    monkeypatch.setattr(
        rhee,
        "load_recent_conversation",
        lambda: "recent",
    )
    monkeypatch.setattr(
        rhee,
        "load_short_term",
        lambda query: ("short", "short_term_sport"),
    )
    monkeypatch.setattr(
        rhee,
        "build_recall_packet",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        rhee,
        "format_memory_packet",
        lambda *args, **kwargs: "long",
    )


def test_build_context_records_privacy_safe_stage_latency(monkeypatch):
    install_fast_context_dependencies(monkeypatch)
    monkeypatch.setattr(rhee.time, "monotonic", StepClock())

    receipt = {}
    context = rhee.build_context(
        "Recall diving Bali",
        evidence_out=[],
        recall_plan=plan(),
        receipt_out=receipt,
    )

    expected_stages = {
        "identity",
        "learnings",
        "indexed_retrieval",
        "raw_continuity",
        "recent_conversation",
        "short_term",
        "recall_ranking",
        "long_term_format",
    }
    assert set(receipt["stage_latency_ms"]) == expected_stages
    assert all(
        isinstance(value, int) and value >= 0
        for value in receipt["stage_latency_ms"].values()
    )
    assert receipt["slowest_stage"] in expected_stages
    assert receipt["slowest_stage_ms"] == receipt["stage_latency_ms"][
        receipt["slowest_stage"]
    ]
    assert receipt["latency_ms"] > 0
    assert "identity" in context
    assert "learnings" in context
    assert "Recall diving Bali" not in str(receipt["stage_latency_ms"])


def test_build_context_keeps_partial_stage_latency_when_indexed_recall_fails(monkeypatch):
    install_fast_context_dependencies(monkeypatch)
    monkeypatch.setattr(rhee.time, "monotonic", StepClock())
    monkeypatch.setattr(
        rhee,
        "search_database_candidates",
        lambda *args, **kwargs: None,
    )

    receipt = {}
    context = rhee.build_context(
        "Recall diving Bali",
        evidence_out=[],
        recall_plan=plan(),
        receipt_out=receipt,
    )

    assert receipt["status"] == "unavailable"
    assert set(receipt["stage_latency_ms"]) == {
        "identity",
        "learnings",
        "indexed_retrieval",
    }
    assert receipt["slowest_stage"] in receipt["stage_latency_ms"]
    assert "Indexed recall unavailable" in context


def test_context_packet_reports_total_and_temporal_latency(monkeypatch):
    monkeypatch.setattr(rhee.time, "monotonic", StepClock())
    monkeypatch.setattr(rhee, "plan_recall", lambda query: plan())

    def build_context(query, evidence_out=None, recall_plan=None, receipt_out=None):
        receipt_out.update(
            status="checked",
            latency_ms=120,
            stage_latency_ms={"indexed_retrieval": 80},
            slowest_stage="indexed_retrieval",
            slowest_stage_ms=80,
        )
        return "context"

    monkeypatch.setattr(rhee, "build_context", build_context)
    monkeypatch.setattr(
        rhee,
        "build_temporal_packet",
        lambda *args, **kwargs: {
            "context": "",
            "evidence": [],
            "receipt": {"status": "checked"},
        },
    )
    monkeypatch.setattr(
        rhee,
        "explicit_deep_recall_requested",
        lambda query: False,
    )
    monkeypatch.setattr(rhee, "deep_recall_requested", lambda query: False)
    monkeypatch.setattr(
        rhee,
        "classify_short_term_domain",
        lambda query: "short_term_sport",
    )

    packet = rhee.build_context_packet("Recall diving Bali")
    receipt = packet["recall_plan"]

    assert receipt["temporal_latency_ms"] >= 0
    assert receipt["packet_latency_ms"] >= receipt["temporal_latency_ms"]
    assert receipt["slowest_stage"] == "indexed_retrieval"
    assert receipt["stage_latency_ms"] == {"indexed_retrieval": 80}
