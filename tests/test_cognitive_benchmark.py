from core.cognition.benchmark import (
    BENCHMARK_DIMENSIONS,
    assess_claim_grounding,
    benchmark_manifest,
    run_cognitive_benchmark,
)


def test_phase_seven_is_exposed_by_the_live_server_contract():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "api" / "server.py").read_text(encoding="utf-8")
    assert '@app.get("/cognition/benchmark")' in source
    assert '"version": "9.0"' in source
    assert '"evaluation": "cognitive_benchmark_v1"' in source
    assert '"benchmark_scores_require_executed_tests": True' in source


def test_phase_seven_manifest_covers_all_canonical_dimensions():
    expected = {
        "recall_accuracy",
        "chronology_accuracy",
        "identity_accuracy",
        "pattern_recognition",
        "current_vs_historical_distinction",
        "contradiction_detection",
        "source_attribution",
        "rike_reasoning_quality",
        "uncertainty_calibration",
        "specialist_routing",
        "false_memory_rate",
        "over_connection_rate",
    }
    manifest = benchmark_manifest()
    assert expected.issubset(set(BENCHMARK_DIMENSIONS))
    assert expected.issubset(set(manifest["dimensions"]))
    assert "reflective_metacognition" in manifest["dimensions"]
    assert manifest["case_count"] >= len(expected)
    assert manifest["scoring"] == "calculated_only_from_executed_case_outcomes"
    assert manifest["external_calls"] is False


def test_phase_seven_suite_executes_and_earns_every_score():
    result = run_cognitive_benchmark()
    assert result["status"] == "passed"
    assert result["overall"]["passed"] == result["overall"]["total"]
    assert result["overall"]["total"] == result["case_count"]
    assert result["overall"]["score_pct"] == 100.0
    assert set(result["metrics"]) == set(BENCHMARK_DIMENSIONS)
    for metric in result["metrics"].values():
        assert metric["total"] >= 1
        assert metric["score_pct"] == 100.0
        assert all(case["passed"] for case in metric["cases"])
        assert all(case["expected"] is not None for case in metric["cases"])
        assert all(case["observed"] is not None for case in metric["cases"])


def test_false_memory_rate_is_derived_from_supplied_claims():
    result = assess_claim_grounding(
        ["Fact A", "Invented Fact B"],
        ["Fact A is directly present in this evidence."],
    )
    assert result["total"] == 2
    assert result["unsupported"] == 1
    assert result["false_memory_rate"] == 0.5


def test_benchmark_failure_is_visible_not_silently_scored(monkeypatch):
    import core.cognition.benchmark as benchmark

    original = benchmark.CASES

    def broken_case():
        raise RuntimeError("deliberate negative control")

    monkeypatch.setattr(
        benchmark,
        "CASES",
        original + (("recall_accuracy", "deliberate_failure", broken_case),),
    )
    result = benchmark.run_cognitive_benchmark()
    assert result["status"] == "failed"
    assert result["overall"]["passed"] < result["overall"]["total"]
    failed = [case for case in result["metrics"]["recall_accuracy"]["cases"] if not case["passed"]]
    assert failed[0]["error"].startswith("RuntimeError:")
