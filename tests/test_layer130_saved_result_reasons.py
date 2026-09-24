"""Collapsed results explain status and empty replies are not available."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['result_reasons', 'empty_answers'])
def test_saved_result_reasons(scenario):
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
