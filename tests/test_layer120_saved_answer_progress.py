"""User-controlled saved-answer review preserves integrity and bounded retrieval."""
import subprocess
import pytest

@pytest.mark.parametrize('scenario', ['newest', 'empty', 'locked', 'mixed',
    'stop_fetch', 'stop_verify', 'account', 'restart'])
def test_saved_answer_review(scenario):
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
