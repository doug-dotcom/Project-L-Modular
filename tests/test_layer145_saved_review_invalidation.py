"""Changed browser history invalidates a review and rejects its late results."""
import subprocess

import pytest


@pytest.mark.parametrize('scenario', [
    'review_change_task', 'review_change_storage', 'review_change_token',
    'review_change_clear', 'review_change_unrelated', 'review_change_late_fetch',
    'review_change_late_verify', 'review_change_closed',
])
def test_saved_review_invalidation(scenario):
    result = subprocess.run(
        ['node', 'tests/saved_answer_review.test.cjs', scenario],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
