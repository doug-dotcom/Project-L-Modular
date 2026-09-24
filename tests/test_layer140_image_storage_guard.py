"""Fallback picture submission preserves unsent prompts and file selection."""
import subprocess
import pytest


@pytest.mark.parametrize('scenario', ['tasks', 'pending', 'malformed'])
def test_image_storage_guard(scenario):
    result = subprocess.run(['node', 'tests/image_storage_guard.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
