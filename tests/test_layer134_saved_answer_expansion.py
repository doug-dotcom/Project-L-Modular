"""Refresh retains individual disclosures without leaking them into a new review."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['refresh_open_questions', 'refresh_older_questions', 'refresh_expansion_reset'])
def test_saved_answer_expansion(scenario):
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
