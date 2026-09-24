"""Saved task status filters use only checked results."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['status_filters', 'status_batches'])
def test_saved_answer_status(scenario):
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
