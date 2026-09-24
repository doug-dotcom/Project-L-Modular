"""Review ordering must remain stable across filtering and batches."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['review_order', 'review_order_batches'])
def test_saved_review_order(scenario):
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
