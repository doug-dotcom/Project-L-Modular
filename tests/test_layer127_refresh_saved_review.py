"""Refresh keeps review settings and isolates superseded work."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['refresh', 'refresh_pending'])
def test_refresh_saved_review(scenario):
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
