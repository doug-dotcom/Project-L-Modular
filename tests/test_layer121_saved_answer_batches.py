"""Older saved task batches preserve ordering, scope and stop guards."""
import subprocess
import pytest

@pytest.mark.parametrize('scenario', ['pagination', 'snapshot', 'cap', 'account_between', 'continue_late'])
def test_saved_answer_batches(scenario):
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
