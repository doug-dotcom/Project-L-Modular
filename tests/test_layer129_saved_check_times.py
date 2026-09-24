"""Review timestamps distinguish batches, refresh and failed attempts."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['check_times', 'check_times_refresh'])
def test_saved_result_check_times(scenario):
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
