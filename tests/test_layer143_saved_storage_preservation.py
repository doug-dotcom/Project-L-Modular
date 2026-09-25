"""Unreadable saved-task data must never become an empty writable history."""
import subprocess

import pytest


@pytest.mark.parametrize('scenario', [
    'json', 'empty', 'null', 'object', 'scalar', 'read_failure',
    'missing', 'valid', 'live_corrupt', 'live_read_failure',
])
def test_saved_storage_preservation(scenario):
    result = subprocess.run(
        ['node', 'tests/saved_storage_preservation.test.cjs', scenario],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stderr
