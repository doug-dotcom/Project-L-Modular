"""Saved-answer review distinguishes damaged history from an empty history."""
import subprocess

import pytest


@pytest.mark.parametrize('scenario', [
    'history_json', 'history_shape', 'history_read_error', 'history_empty',
    'history_missing', 'history_mixed', 'history_invalid', 'history_refresh',
])
def test_saved_history_status(scenario):
    result = subprocess.run(
        ['node', 'tests/saved_answer_review.test.cjs', scenario],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
