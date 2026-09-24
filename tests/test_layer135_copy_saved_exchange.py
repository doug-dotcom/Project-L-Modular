"""Combined copying keeps question context and delivery safeguards."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['copy_exchange', 'copy_exchange_gates', 'copy_exchange_stale'])
def test_copy_saved_exchange(scenario):
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
