"""Search only checked, verified display content without additional requests."""
import subprocess
import pytest

@pytest.mark.parametrize('scenario', ['search', 'attention', 'rejected_search', 'batch_filter'])
def test_saved_answer_search(scenario):
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
