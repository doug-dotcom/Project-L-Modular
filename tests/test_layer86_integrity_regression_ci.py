from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def layer_test_files():
    return sorted(
        (ROOT / "tests").glob("test_layer*.py"),
        key=lambda path: (
            int(re.search(r"test_layer(\d+)", path.name).group(1)),
            path.name,
        ),
    )


def layer_numbers():
    return [
        int(re.search(r"test_layer(\d+)", path.name).group(1))
        for path in layer_test_files()
    ]


def test_layer86_ci_uses_numbered_layer_wildcard():
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "tests/test_layer*.py" in source
    assert source.count("tests/test_layer*.py") == 1


def test_layer86_ci_no_longer_manually_enumerates_numbered_layers():
    source = WORKFLOW.read_text(encoding="utf-8")

    explicit = re.findall(r"tests/test_layer\d+[^\s]*\.py", source)
    assert explicit == []


def test_layer86_integrity_layers_are_continuous_from_68_to_current():
    numbers = layer_numbers()

    assert numbers
    assert numbers[0] == 68
    assert numbers == list(range(68, max(numbers) + 1))


def test_layer86_each_integrity_layer_has_exactly_one_regression_file():
    numbers = layer_numbers()

    assert len(numbers) == len(set(numbers))


def test_layer86_wildcard_includes_this_layer_automatically():
    names = [path.name for path in layer_test_files()]

    assert "test_layer86_integrity_regression_ci.py" in names


def test_layer86_core_active_suite_remains_present_alongside_layer_glob():
    source = WORKFLOW.read_text(encoding="utf-8")

    required = {
        "tests/test_build_hardening.py",
        "tests/test_cognitive_core.py",
        "tests/test_evidence_evaluation.py",
        "tests/test_modern_models.py",
        "tests/test_model_independence.py",
        "tests/test_temporal_memory.py",
    }
    assert all(item in source for item in required)

    model_idx = source.index("tests/test_model_independence.py")
    layer_idx = source.index("tests/test_layer*.py")
    temporal_idx = source.index("tests/test_temporal_memory.py")
    assert model_idx < layer_idx < temporal_idx


def test_layer86_ci_step_name_reports_both_core_and_layer_suites():
    source = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "Run active memory and numbered-layer regression suites"
        in source
    )
