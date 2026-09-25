"""Malformed or stale history must not hide usable saved file answers."""
import subprocess

import pytest


@pytest.mark.parametrize('scenario', [
    'mixed', 'allbad', 'empty', 'missing', 'wrong', 'failure', 'race', 'race_error', 'answer',
])
def test_file_history_resilience(scenario):
    result = subprocess.run(['node', 'tests/file_history_resilience.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
