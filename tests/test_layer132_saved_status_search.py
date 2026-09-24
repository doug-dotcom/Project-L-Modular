"""Search supports status labels and explains empty filtered results."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['status_search', 'empty_search_guidance'])
def test_saved_status_search(scenario):
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
