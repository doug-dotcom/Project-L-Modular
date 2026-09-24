"""Clipboard writes remain serial across buttons, batches and refreshes."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['copy_serialised', 'copy_serialised_refresh', 'copy_serialised_failure'])
def test_saved_copy_coordination(scenario):
    result = subprocess.run(['node', 'tests/saved_answer_review.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
