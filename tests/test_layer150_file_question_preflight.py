"""File questions prepare a valid recovery handle before submission or UI changes."""
import subprocess

import pytest


@pytest.mark.parametrize('scenario', [
    'read', 'write', 'json', 'null', 'array', 'number', 'missing', 'invalid',
    'uuid', 'uuidinvalid', 'reuse', 'different',
])
def test_file_question_preflight(scenario):
    result = subprocess.run(['node', 'tests/file_question_preflight.test.cjs', scenario],
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
