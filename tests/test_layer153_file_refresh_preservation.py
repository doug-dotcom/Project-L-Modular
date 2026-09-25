"""Refreshing the file list preserves available immutable file views and recovery."""
import subprocess

import pytest


@pytest.mark.parametrize('scenario', [
    'keep', 'pending', 'upload', 'race', 'race_error', 'page',
    'missing', 'invalid', 'envelope', 'error',
])
def test_file_refresh_preservation(scenario):
    result = subprocess.run(['node', 'tests/file_refresh_preservation.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
