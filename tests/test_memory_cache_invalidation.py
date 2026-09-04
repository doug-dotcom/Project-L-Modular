from pathlib import Path

from memory.retrieval.cache_state import (
    cache_generation,
    invalidate_recall_caches,
)


def test_raw_and_long_term_generations_advance_independently():
    raw_before = cache_generation("raw")
    long_before = cache_generation("long_term")

    after_raw = invalidate_recall_caches(raw=True)
    assert after_raw["raw"] == raw_before + 1
    assert after_raw["long_term"] == long_before

    after_long = invalidate_recall_caches(long_term=True)
    assert after_long["raw"] == raw_before + 1
    assert after_long["long_term"] == long_before + 1


def test_unspecified_invalidation_safely_advances_both_generations():
    before = {
        "raw": cache_generation("raw"),
        "long_term": cache_generation("long_term"),
    }

    after = invalidate_recall_caches()

    assert after == {
        "raw": before["raw"] + 1,
        "long_term": before["long_term"] + 1,
    }


def test_unknown_cache_name_is_rejected():
    try:
        cache_generation("short_term")
    except ValueError as exc:
        assert "Unknown recall cache" in str(exc)
    else:
        raise AssertionError("Unknown cache names must fail closed")


def test_every_live_memory_writer_invalidates_its_recall_layer():
    root = Path(__file__).resolve().parents[1]
    expected_hooks = {
        "api/server.py": "invalidate_recall_caches(raw=True)",
        "core/cognition/brain_pipeline.py": "invalidate_recall_caches(long_term=True)",
        "agents/carol/carol.py": "invalidate_recall_caches(long_term=True)",
    }
    for relative_path, hook in expected_hooks.items():
        source = (root / relative_path).read_text(encoding="utf-8")
        assert hook in source
