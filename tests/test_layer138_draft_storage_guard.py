"""Local persistence failures must retain the draft and avoid submission."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['token', 'tasks', 'pending', 'malformed'])
def test_draft_storage_guard(scenario):
    result = subprocess.run(['node', 'tests/draft_storage_guard.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
