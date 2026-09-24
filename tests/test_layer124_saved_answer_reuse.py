"""Reuse only verified answers and never overwrite or send a draft."""
import subprocess
import pytest

@pytest.mark.parametrize('scenario', ['reuse_question', 'copy_answer', 'copy_rejected'])
def test_saved_answer_reuse(scenario):
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
