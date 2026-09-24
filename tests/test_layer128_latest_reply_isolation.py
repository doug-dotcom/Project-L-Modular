"""Saved review must not replace the latest chat reply used for speech."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['latest_reply', 'latest_reply_empty'])
def test_saved_review_preserves_latest_reply(scenario):
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
