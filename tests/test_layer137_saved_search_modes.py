"""Saved search supports all-word and exact-phrase matching locally."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['search_words', 'search_phrase', 'search_mode_refresh'])
def test_saved_search_modes(scenario):
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
