"""Question copying preserves drafts and ignores stale review controls."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['copy_question', 'copy_question_blocked', 'copy_question_empty'])
def test_copy_saved_question(scenario):
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
